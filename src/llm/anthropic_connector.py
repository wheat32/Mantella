"""Connects Mantella directly to the Claude API (https://api.anthropic.com) using the official Anthropic SDK.

The rest of Mantella speaks the OpenAI chat format (messages, tools and streamed results). This module translates
between that format and the Claude Messages API, so that Claude can be used without going through OpenRouter,
with prompt caching applied the way the Claude API expects it.
"""
import json
import logging
from collections import OrderedDict
from typing import Any, AsyncGenerator

logger = logging.getLogger("Mantella")

ANTHROPIC_BASE_URL = 'https://api.anthropic.com'


class AnthropicConnector:
    # Thinking counts towards max_tokens on Claude models, so room for it is added on top of the response length the user configured
    THINKING_HEADROOM_TOKENS = 2048
    DEFAULT_MAX_TOKENS = 250
    # Dialogue is short and latency-sensitive, so the lowest effort is used unless set otherwise via the "effort" LLM parameter
    DEFAULT_EFFORT = 'low'
    # Models for which the API can hand a request declined by the model's safety classifiers to another Claude model
    REFUSAL_FALLBACK_MODEL_PREFIXES = ('claude-fable-5-2', 'claude-fable-5-1', 'claude-opus-5-5', 'claude-opus-5', 'claude-sonnet-5-5')
    REFUSAL_FALLBACK_BETA = 'server-side-fallback-2026-07-01'
    FIRST_MESSAGE_PLACEHOLDER = '(The conversation begins.)'

    def __init__(self, api_key: str | None, timeout: float = 60.0, max_retries: int = 2) -> None:
        self.__api_key = api_key
        self.__timeout = timeout
        self.__max_retries = max_retries
        # The unmodified content of assistant turns that called tools (including their thinking blocks), by the id of their first tool call.
        # Claude requires these blocks to be passed back unchanged while the results of the tools are being returned
        self.__tool_turns: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()

    @staticmethod
    def is_applicable(base_url: str) -> bool:
        return (base_url or '').strip().lower().rstrip('/').startswith(ANTHROPIC_BASE_URL)

    # ---------------------------------------------------------------- requests

    async def stream(self, model: str, openai_messages: list[dict[str, Any]], request_params: dict[str, Any] | None,
                     tools: list[dict[str, Any]] | None, caching_enabled: bool) -> AsyncGenerator[tuple[str, str | list], None]:
        """Streams a response, yielding ("content", text) for text as it arrives and ("tool_calls", [...]) in the OpenAI format at the end"""
        import anthropic

        request = self.build_request(model, openai_messages, request_params, tools, caching_enabled)
        async with anthropic.AsyncAnthropic(api_key=self.__api_key, timeout=self.__timeout, max_retries=self.__max_retries) as client:
            async with self.__get_messages_api(client, request).stream(**request) as stream:
                async for text in stream.text_stream:
                    if text:
                        yield ("content", text)
                final_message = await stream.get_final_message()

        self.__log_usage(final_message)
        self.__warn_about_stop_reason(final_message)
        tool_calls = self.__get_tool_calls(final_message)
        if tool_calls:
            yield ("tool_calls", tool_calls)

    def complete(self, model: str, openai_messages: list[dict[str, Any]], request_params: dict[str, Any] | None, caching_enabled: bool) -> str | None:
        """Returns the full text of a response (used for eg conversation summaries)"""
        import anthropic

        request = self.build_request(model, openai_messages, request_params, None, caching_enabled)
        with anthropic.Anthropic(api_key=self.__api_key, timeout=max(self.__timeout, 120.0), max_retries=self.__max_retries) as client:
            message = self.__get_messages_api(client, request).create(**request)

        self.__log_usage(message)
        self.__warn_about_stop_reason(message)
        text = ''.join(block.text for block in message.content if block.type == 'text')
        return text or None

    @staticmethod
    def __get_messages_api(client, request: dict[str, Any]):
        # refusal fallbacks are a beta feature, served by the beta endpoint
        return client.beta.messages if 'betas' in request else client.messages

    def build_request(self, model: str, openai_messages: list[dict[str, Any]], request_params: dict[str, Any] | None,
                      tools: list[dict[str, Any]] | None, caching_enabled: bool) -> dict[str, Any]:
        """Builds the arguments of a Claude Messages API request out of an OpenAI style request"""
        params = dict(request_params or {})
        model = model.split('/')[-1] # allow OpenRouter style names (eg "anthropic/claude-haiku-5-5")
        system_text, messages = self.convert_messages(openai_messages)

        try:
            response_tokens = int(params.get('max_tokens', self.DEFAULT_MAX_TOKENS))
        except (TypeError, ValueError):
            response_tokens = self.DEFAULT_MAX_TOKENS

        request: dict[str, Any] = {
            'model': model,
            'max_tokens': response_tokens + self.THINKING_HEADROOM_TOKENS,
            'messages': messages,
            'output_config': {'effort': str(params.get('effort', self.DEFAULT_EFFORT))},
        }
        if isinstance(params.get('thinking'), dict):
            request['thinking'] = params['thinking']

        if system_text:
            system_block: dict[str, Any] = {'type': 'text', 'text': system_text}
            if caching_enabled:
                # The system prompt only changes when the NPCs in the conversation change. Its own breakpoint keeps it
                # cached no matter what happens to the conversation history after it
                system_block['cache_control'] = {'type': 'ephemeral', 'ttl': '1h'}
            request['system'] = [system_block]
        if caching_enabled:
            # Automatic caching of the growing conversation: each request reads what the previous one wrote
            request['cache_control'] = {'type': 'ephemeral'}

        stop = params.get('stop')
        if isinstance(stop, str):
            stop = [stop]
        if isinstance(stop, list):
            stop_sequences = [s for s in stop if isinstance(s, str) and s.strip()] # whitespace-only stop sequences are rejected
            if stop_sequences:
                request['stop_sequences'] = stop_sequences

        claude_tools = self.convert_tools(tools)
        if claude_tools:
            request['tools'] = claude_tools

        if params.get('refusal_fallback', True) and model.startswith(self.REFUSAL_FALLBACK_MODEL_PREFIXES):
            request['betas'] = [self.REFUSAL_FALLBACK_BETA]
            request['fallbacks'] = 'default'

        # Sampling parameters (temperature, top_p, ...) and other OpenAI / OpenRouter specific parameters are not sent:
        # current Claude models reject them
        return request

    # ---------------------------------------------------------------- conversions

    def convert_messages(self, openai_messages: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
        """Converts OpenAI style messages into the system prompt and the messages of a Claude request"""
        system_parts: list[str] = []
        messages: list[dict[str, Any]] = []
        last_tool_turn_index = self.__get_index_of_pending_tool_turn(openai_messages)

        for index, message in enumerate(openai_messages):
            role = message.get('role')
            content = message.get('content')

            if role == 'system':
                text = self.__get_text(content)
                if not messages:
                    if text:
                        system_parts.append(text)
                elif text: # an instruction in the middle of the conversation
                    self.__append(messages, 'user', [{'type': 'text', 'text': f'[{text}]'}])
            elif role == 'tool':
                self.__append(messages, 'user', [{
                    'type': 'tool_result',
                    'tool_use_id': str(message.get('tool_call_id', '')),
                    'content': self.__get_text(content) or 'Done.',
                }])
            elif role == 'assistant':
                blocks = self.__convert_assistant_message(message, replay_original=(index == last_tool_turn_index))
                if blocks:
                    messages.append({'role': 'assistant', 'content': blocks})
            else:
                blocks = self.__convert_content(content)
                if blocks:
                    self.__append(messages, 'user', blocks)

        # Claude expects the conversation to start with a user message (which eg conversations between NPCs do not)
        if not messages or messages[0]['role'] != 'user':
            messages.insert(0, {'role': 'user', 'content': [{'type': 'text', 'text': self.FIRST_MESSAGE_PLACEHOLDER}]})
        return '\n\n'.join(system_parts), messages

    @staticmethod
    def __append(messages: list[dict[str, Any]], role: str, blocks: list[dict[str, Any]]) -> None:
        """Adds content to the conversation, merging it into the previous message if that has the same role.
        All results of the tools called in one turn have to be returned in a single user message"""
        if messages and messages[-1]['role'] == role:
            messages[-1]['content'].extend(blocks)
        else:
            messages.append({'role': role, 'content': list(blocks)})

    @staticmethod
    def __get_index_of_pending_tool_turn(openai_messages: list[dict[str, Any]]) -> int | None:
        """The index of the assistant message whose tool calls are being answered by this request, if there is one"""
        for index in range(len(openai_messages) - 1, -1, -1):
            role = openai_messages[index].get('role')
            if role == 'tool':
                continue
            if role == 'assistant' and openai_messages[index].get('tool_calls') and index < len(openai_messages) - 1:
                return index
            return None
        return None

    def __convert_assistant_message(self, message: dict[str, Any], replay_original: bool) -> list[dict[str, Any]]:
        tool_calls = message.get('tool_calls') or []
        if replay_original and tool_calls:
            original_blocks = self.__tool_turns.get(str(tool_calls[0].get('id', '')))
            if original_blocks:
                return [dict(block) for block in original_blocks]

        blocks: list[dict[str, Any]] = []
        text = self.__get_text(message.get('content'))
        if text.strip():
            blocks.append({'type': 'text', 'text': text})
        for tool_call in tool_calls:
            function = tool_call.get('function', {})
            try:
                arguments = json.loads(function.get('arguments') or '{}')
            except (TypeError, ValueError):
                arguments = {}
            blocks.append({
                'type': 'tool_use',
                'id': str(tool_call.get('id', '')),
                'name': str(function.get('name', '')),
                'input': arguments if isinstance(arguments, dict) else {},
            })
        return blocks

    @staticmethod
    def __get_text(content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return '\n'.join(str(part.get('text', '')) for part in content if isinstance(part, dict) and part.get('type') == 'text')
        return '' if content is None else str(content)

    @staticmethod
    def __convert_content(content: Any) -> list[dict[str, Any]]:
        """Converts the content of a user message (text and images) into Claude content blocks"""
        if isinstance(content, str):
            return [{'type': 'text', 'text': content}] if content.strip() else []
        if not isinstance(content, list):
            return [{'type': 'text', 'text': str(content)}] if content else []

        blocks: list[dict[str, Any]] = []
        for part in content:
            if not isinstance(part, dict):
                continue
            if part.get('type') == 'text' and str(part.get('text', '')).strip():
                blocks.append({'type': 'text', 'text': str(part['text'])})
            elif part.get('type') == 'image_url':
                image_url = part.get('image_url')
                url = image_url.get('url', '') if isinstance(image_url, dict) else str(image_url or '')
                if url.startswith('data:') and ';base64,' in url:
                    media_type, data = url[len('data:'):].split(';base64,', 1)
                    blocks.append({'type': 'image', 'source': {'type': 'base64', 'media_type': media_type or 'image/jpeg', 'data': data}})
                elif url:
                    blocks.append({'type': 'image', 'source': {'type': 'url', 'url': url}})
        # images go before the text that refers to them
        return [b for b in blocks if b['type'] == 'image'] + [b for b in blocks if b['type'] != 'image']

    @staticmethod
    def convert_tools(tools: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
        """Converts OpenAI style function definitions into Claude tool definitions"""
        claude_tools: list[dict[str, Any]] = []
        for tool in tools or []:
            function = tool.get('function', tool)
            name = function.get('name')
            if not name:
                continue
            claude_tools.append({
                'name': name,
                'description': function.get('description', ''),
                'input_schema': function.get('parameters') or {'type': 'object', 'properties': {}},
            })
        return claude_tools

    def __get_tool_calls(self, message) -> list[dict[str, Any]]:
        """Returns the tools Claude wants to call in the OpenAI format, and remembers the turn so that it can be passed back unchanged"""
        tool_calls: list[dict[str, Any]] = []
        for block in message.content:
            if block.type == 'tool_use':
                tool_calls.append({
                    'id': block.id,
                    'type': 'function',
                    'function': {'name': block.name, 'arguments': json.dumps(block.input or {})},
                })
        if tool_calls:
            self.__tool_turns[tool_calls[0]['id']] = [block.model_dump(exclude_none=True) for block in message.content]
            while len(self.__tool_turns) > 20:
                self.__tool_turns.popitem(last=False)
        return tool_calls

    # ---------------------------------------------------------------- reporting

    @staticmethod
    def __log_usage(message) -> None:
        usage = getattr(message, 'usage', None)
        if not usage:
            return
        cache_read = getattr(usage, 'cache_read_input_tokens', 0) or 0
        cache_written = getattr(usage, 'cache_creation_input_tokens', 0) or 0
        logger.debug(f'Claude usage: {usage.input_tokens} input tokens, {usage.output_tokens} output tokens, '
                     f'{cache_read} read from cache, {cache_written} written to cache')

    @staticmethod
    def __warn_about_stop_reason(message) -> None:
        stop_reason = getattr(message, 'stop_reason', None)
        if stop_reason == 'refusal':
            details = getattr(message, 'stop_details', None)
            category = getattr(details, 'category', None)
            logger.warning(f"Claude declined to respond to this request{f' (category: {category})' if category else ''}. Try rephrasing, or select a different model")
        elif stop_reason == 'max_tokens':
            logger.warning('The response of Claude was cut off because it reached the maximum response length. Increase "max_tokens" in `Large Language Model`->`Parameters` in the Mantella UI if this happens often')

    @staticmethod
    def get_models(api_key: str) -> list[tuple[str, str, int | None]]:
        """Returns the available Claude models as (display name, model id, context size)"""
        import anthropic
        with anthropic.Anthropic(api_key=api_key, timeout=20.0) as client:
            return [(model.display_name, model.id, getattr(model, 'max_input_tokens', None)) for model in client.models.list()]
