import json
from types import SimpleNamespace
from src.llm.anthropic_connector import AnthropicConnector


def test_is_applicable():
    assert AnthropicConnector.is_applicable('https://api.anthropic.com')
    assert AnthropicConnector.is_applicable('https://api.anthropic.com/v1/')
    assert not AnthropicConnector.is_applicable('https://openrouter.ai/api/v1')
    assert not AnthropicConnector.is_applicable('')


def test_convert_messages_extracts_system_prompt():
    system, messages = AnthropicConnector(None).convert_messages([
        {'role': 'system', 'content': 'You are Ralof.'},
        {'role': 'user', 'content': 'Hello'},
        {'role': 'assistant', 'content': 'Hail, friend.'},
        {'role': 'user', 'content': 'Where are we?'},
    ])
    assert system == 'You are Ralof.'
    assert [m['role'] for m in messages] == ['user', 'assistant', 'user']
    assert messages[0]['content'] == [{'type': 'text', 'text': 'Hello'}]


def test_conversation_always_starts_with_user_message():
    _, messages = AnthropicConnector(None).convert_messages([
        {'role': 'system', 'content': 'A conversation between NPCs.'},
        {'role': 'assistant', 'content': 'Lydia: Quiet night.'},
    ])
    assert messages[0]['role'] == 'user'
    assert messages[1] == {'role': 'assistant', 'content': [{'type': 'text', 'text': 'Lydia: Quiet night.'}]}


def test_convert_messages_with_image():
    _, messages = AnthropicConnector(None).convert_messages([
        {'role': 'user', 'content': [
            {'type': 'text', 'text': 'What do you see?'},
            {'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,QUJD', 'detail': 'low'}},
        ]},
    ])
    assert messages[0]['content'] == [
        {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': 'QUJD'}},
        {'type': 'text', 'text': 'What do you see?'},
    ]


def test_convert_messages_with_tool_calls_and_results():
    _, messages = AnthropicConnector(None).convert_messages([
        {'role': 'user', 'content': 'Follow me.'},
        {'role': 'assistant', 'content': None, 'tool_calls': [
            {'id': 'call_1', 'type': 'function', 'function': {'name': 'follow', 'arguments': '{"target": "player"}'}},
            {'id': 'call_2', 'type': 'function', 'function': {'name': 'wave', 'arguments': ''}},
        ]},
        {'role': 'tool', 'tool_call_id': 'call_1', 'content': 'Now following.'},
        {'role': 'tool', 'tool_call_id': 'call_2', 'content': ''},
    ])
    assert messages[1]['content'] == [
        {'type': 'tool_use', 'id': 'call_1', 'name': 'follow', 'input': {'target': 'player'}},
        {'type': 'tool_use', 'id': 'call_2', 'name': 'wave', 'input': {}},
    ]
    # the results of all tools called in one turn are returned in a single user message
    assert messages[2]['role'] == 'user'
    assert [b['tool_use_id'] for b in messages[2]['content']] == ['call_1', 'call_2']
    assert messages[2]['content'][1]['content'] == 'Done.'
    assert len(messages) == 3


def test_tool_turn_is_replayed_unchanged_while_its_results_are_returned():
    connector = AnthropicConnector(None)
    thinking = SimpleNamespace(type='thinking', model_dump=lambda exclude_none=True: {'type': 'thinking', 'thinking': '', 'signature': 'sig'})
    tool_use = SimpleNamespace(type='tool_use', id='toolu_1', name='follow', input={'target': 'player'},
                               model_dump=lambda exclude_none=True: {'type': 'tool_use', 'id': 'toolu_1', 'name': 'follow', 'input': {'target': 'player'}})
    tool_calls = connector._AnthropicConnector__get_tool_calls(SimpleNamespace(content=[thinking, tool_use]))
    assert tool_calls == [{'id': 'toolu_1', 'type': 'function', 'function': {'name': 'follow', 'arguments': json.dumps({'target': 'player'})}}]

    history = [
        {'role': 'user', 'content': 'Follow me.'},
        {'role': 'assistant', 'content': None, 'tool_calls': tool_calls},
        {'role': 'tool', 'tool_call_id': 'toolu_1', 'content': 'Now following.'},
    ]
    _, messages = connector.convert_messages(history)
    assert messages[1]['content'][0] == {'type': 'thinking', 'thinking': '', 'signature': 'sig'}

    # once the conversation has moved on, the turn is sent without its thinking blocks
    _, messages = connector.convert_messages(history + [{'role': 'assistant', 'content': 'Lead the way.'}, {'role': 'user', 'content': 'Good.'}])
    assert [b['type'] for b in messages[1]['content']] == ['tool_use']


def test_build_request():
    connector = AnthropicConnector(None)
    request = connector.build_request(
        'anthropic/claude-haiku-5-5',
        [{'role': 'system', 'content': 'You are Ralof.'}, {'role': 'user', 'content': 'Hello'}],
        {'max_tokens': 250, 'temperature': 1.0, 'stop': ['#', ' '], 'effort': 'medium'},
        [{'type': 'function', 'function': {'name': 'follow', 'description': 'Follow the player', 'parameters': {'type': 'object', 'properties': {}}}}],
        caching_enabled=True)

    assert request['model'] == 'claude-haiku-5-5'
    assert request['max_tokens'] == 250 + AnthropicConnector.THINKING_HEADROOM_TOKENS
    assert request['output_config'] == {'effort': 'medium'}
    assert request['system'] == [{'type': 'text', 'text': 'You are Ralof.', 'cache_control': {'type': 'ephemeral', 'ttl': '1h'}}]
    assert request['cache_control'] == {'type': 'ephemeral'}
    assert request['stop_sequences'] == ['#']
    assert request['tools'] == [{'name': 'follow', 'description': 'Follow the player', 'input_schema': {'type': 'object', 'properties': {}}}]
    assert 'temperature' not in request
    assert 'fallbacks' not in request # no server-side refusal fallback for Haiku


def test_build_request_defaults():
    connector = AnthropicConnector(None)
    request = connector.build_request('claude-opus-5-5', [{'role': 'user', 'content': 'Hello'}], None, None, caching_enabled=False)
    assert request['output_config'] == {'effort': 'low'}
    assert 'system' not in request and 'cache_control' not in request and 'tools' not in request
    assert request['betas'] == [AnthropicConnector.REFUSAL_FALLBACK_BETA] and request['fallbacks'] == 'default'

    request = connector.build_request('claude-opus-5-5', [{'role': 'user', 'content': 'Hello'}], {'refusal_fallback': False}, None, caching_enabled=False)
    assert 'betas' not in request and 'fallbacks' not in request
