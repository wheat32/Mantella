from typing import Any, Dict, List
import json
import logging


class ClaudeCacheConnector:
    """Adds Anthropic prompt-caching for Claude models via OpenRouter.

    - Automatically active when using OpenRouter with a Claude model.
    - Converts messages into Claude-compatible content blocks and applies two cache
      breakpoints: one on the system prompt, and a moving one on the message before the newest message,
      so that the conversation history (including assistant responses) is cached while the newest input is not.

    Caching strategy:
    - Turn 1: system [cached] + user_new
    - Turn 2+: system [cached] + ... + assistant_previous [cached] + user_new

    Note that Claude only caches prompts above a minimum size (1024 - 4096 tokens depending on the model).
    Shorter prompts are silently not cached.

    This maximizes cache reuse as the conversation grows.
    """

    # The system prompt is written to the cache once per conversation and read on every turn, so the longer (pricier to write) lifetime pays off.
    # Breakpoints with a longer lifetime have to come before shorter ones, which the order system prompt -> conversation satisfies
    SYSTEM_CACHE_TTL = "1h"
    # The conversation history is written anew on every turn. The default lifetime is the cheapest to write (1.25x instead of 2x),
    # and is refreshed each time it is read
    CONVERSATION_CACHE_TTL = "5m"

    def is_applicable(self, base_url: str, model_name: str) -> bool:
        is_openrouter = base_url.strip().lower().startswith("https://openrouter.ai/")

        name = (model_name or "").strip().lower()
        is_claude_model = "claude" in name

        return is_openrouter and is_claude_model

    def transform_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not messages:
            return messages

        transformed: List[Dict[str, Any]] = [dict(message) for message in messages]

        # Breakpoint 1: the system prompt. It only changes when the NPCs in the conversation change,
        # so it stays cached even when something invalidates the cached conversation history
        # (and it is the only thing that can be cached on a turn that the moving breakpoint below does not cover)
        if transformed[0].get("role") == "system":
            self._mark_message(transformed, 0, self.SYSTEM_CACHE_TTL)

        # Breakpoint 2: the conversation so far, up to the message before the newest one
        cache_index = self._get_cache_target_index(transformed)
        if cache_index is not None and cache_index != 0:
            self._mark_message(transformed, cache_index, self.CONVERSATION_CACHE_TTL)

        return transformed

    def _mark_message(self, messages: List[Dict[str, Any]], index: int, ttl: str) -> None:
        target_message = messages[index]
        target_message["content"] = self._normalize_content(target_message.get("content"))
        self._apply_cache_control(target_message, ttl)
        logging.debug(
            f"Claude cache: breakpoint ({ttl}) at message {index+1}/{len(messages)} "
            f"(role={target_message.get('role')}), caching all messages up to this point"
        )

    def _normalize_content(self, content: Any) -> List[Dict[str, Any]]:
        """Convert any content format into a list of content blocks (dicts).
        
        Claude's caching API requires content to be a list of typed blocks.
        Plain string content or unexpected formats are wrapped accordingly.
        """
        if isinstance(content, list):
            normalized: List[Dict[str, Any]] = []
            for part in content:
                if isinstance(part, dict):
                    normalized_part = dict(part)
                    normalized_part.pop("cache_control", None) # clear stale markers
                    normalized.append(normalized_part)
                else:
                    normalized.append({"type": "text", "text": str(part)})
            return normalized

        if isinstance(content, str) or content is None:
            text_value = content if isinstance(content, str) else ""
            return [{"type": "text", "text": text_value}]

        return [{"type": "text", "text": json.dumps(content, ensure_ascii=False)}]

    def _get_cache_target_index(self, messages: List[Dict[str, Any]]) -> int | None:
        """Find the index of the message to apply the moving cache breakpoint to.

        Everything before the newest message is identical to what the next request will send, so the breakpoint
        goes on the message just before it. This also covers requests that do not end in a user message
        (eg the follow-up request after a tool call), which previously were not cached at all.
        The content of the newest message itself can still change (eg in-game events, vision), so it is left out
        """
        if len(messages) < 2:
            return None

        for idx in range(len(messages) - 2, -1, -1):
            role = messages[idx].get("role")
            if role in ("user", "assistant") and messages[idx].get("content"):
                return idx
            if role == "system":
                return idx

        logging.debug("Claude cache: no suitable message found to cache")
        return None

    def _apply_cache_control(self, message: Dict[str, Any], ttl: str = "5m") -> None:
        """Attach cache_control to the last text block in the message."""
        contents = message.get("content", [])
        for idx in range(len(contents) - 1, -1, -1):
            part = contents[idx]
            if isinstance(part, dict) and part.get("type") == "text":
                updated_part = dict(part)
                updated_part["cache_control"] = {"type": "ephemeral", "ttl": ttl}
                contents[idx] = updated_part
                message["content"] = contents
                logging.debug(f"Claude cache: added cache_control to text block at index {idx}")
                return

        # Fallback: append an empty text block with cache_control
        contents.append({"type": "text", "text": " ", "cache_control": {"type": "ephemeral", "ttl": ttl}})
        message["content"] = contents
        logging.debug("Claude cache: appended empty text block with cache_control")
