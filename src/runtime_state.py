"""Small pieces of state shared between otherwise unrelated parts of Mantella (eg the conversation and the settings UI)"""
import threading

_lock = threading.Lock()
_is_conversation_active: bool = False


def set_conversation_active(is_active: bool) -> None:
    global _is_conversation_active
    with _lock:
        _is_conversation_active = is_active


def is_conversation_active() -> bool:
    with _lock:
        return _is_conversation_active
