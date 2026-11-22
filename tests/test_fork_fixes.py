"""Tests for fixes around paths, file names, token limits and screenshots"""
import numpy as np
import src.utils as utils
from src.config.definitions.tts_definitions import TTSDefinitions
from src.config.types.config_value_path import ConfigValuePath
from src.image.image_manager import ImageManager
from src.tts.ttsable import TTSable


def test_unused_path_is_not_validated(tmp_path):
    required = {"value": False}
    path_value = ConfigValuePath("some_folder", "Some Folder", "", "C:\\does\\not\\exist", "some.exe", is_required=lambda: required["value"])

    assert path_value.does_value_cause_error("C:\\does\\not\\exist").is_success
    assert path_value.parse("Z:\\also\\missing").is_success
    assert path_value.value == "Z:\\also\\missing"

    required["value"] = True
    assert not path_value.does_value_cause_error("C:\\does\\not\\exist").is_success


def test_path_is_validated_by_default():
    path_value = ConfigValuePath("some_folder", "Some Folder", "", "C:\\does\\not\\exist", None)
    assert not path_value.does_value_cause_error("C:\\does\\not\\exist").is_success


def test_tts_folder_requirements():
    assert TTSDefinitions.is_xvasynth_folder_required("xVASynth")
    assert not TTSDefinitions.is_xvasynth_folder_required("Piper")
    assert TTSDefinitions.is_xtts_folder_required("XTTS", "http://127.0.0.1:8020")
    assert TTSDefinitions.is_xtts_folder_required("XTTS", "http://localhost:8020")
    assert not TTSDefinitions.is_xtts_folder_required("XTTS", "http://192.168.1.50:8020") # XTTS running on another machine
    assert not TTSDefinitions.is_xtts_folder_required("Piper", "http://127.0.0.1:8020")


def test_voiceline_file_name_is_ascii_safe():
    name = TTSable._get_voiceline_file_name("MaleNord", "Wait — you’re the “Dragonborn”? Skål!")
    assert name.isascii()
    assert not any(c in name for c in '\\/:*?"<>|.')
    assert name.startswith("MaleNord Wait")
    # different voicelines never share a file name, even if their readable part is identical
    assert name != TTSable._get_voiceline_file_name("MaleNord", "Wait - you're the Dragonborn? Skal!")
    assert len(TTSable._get_voiceline_file_name("MaleNord", "word " * 200)) < 120


def test_known_model_family_token_limit():
    assert utils.get_known_model_family_token_limit("claude-haiku-5-5") == 200_000
    assert utils.get_known_model_family_token_limit("anthropic/claude-sonnet-4.5:beta") == 200_000
    assert utils.get_known_model_family_token_limit("gemma-4-26b-a4b-it") is None
    assert utils.get_known_model_family_token_limit("") is None


def test_blank_screenshot_detection():
    black = np.zeros((100, 100, 4), dtype=np.uint8)
    black[..., 3] = 255 # an opaque alpha channel does not count as content
    assert ImageManager._is_blank(black)

    nearly_black = black.copy()
    nearly_black[0, 0, :3] = 255 # a stray lit pixel (eg a mouse cursor)
    assert ImageManager._is_blank(nearly_black)

    dark_scene = np.full((100, 100, 4), 10, dtype=np.uint8)
    dark_scene[40:60, 40:60, :3] = 90 # a dim torch in a dark dungeon
    assert not ImageManager._is_blank(dark_scene)
    assert ImageManager._is_blank(np.array([]))


def test_trim_oldest_memories_single_npc():
    from src.conversation.context import Context
    memories = "Below is a summary of past events:\n" + "\n".join(
        line for day in range(1, 10) for line in (f"[Day {day}, 9 in the morning]", f"Memory {day}."))

    trimmed, removed = Context.trim_oldest_memories(memories)
    assert removed == 1
    assert "Memory 1." not in trimmed and "[Day 1, 9 in the morning]" not in trimmed
    assert trimmed.startswith("Below is a summary of past events:\n[Day 2, 9 in the morning]\nMemory 2.")

    # the most recent memory is never removed here
    while removed:
        memories, removed = Context.trim_oldest_memories(memories)
    assert memories == "Below is a summary of past events:\n[Day 9, 9 in the morning]\nMemory 9."


def test_trim_oldest_memories_keeps_npc_markers():
    from src.conversation.context import Context
    memories = ("Below is a summary of past events:\n"
                "[This is the beginning of Lydia's memory]\nLydia 1.\nLydia 2.\n[This is the end of Lydia's memory]\n\n"
                "[This is the beginning of Ralof's memory]\nRalof 1.\n[This is the end of Ralof's memory]")
    trimmed, removed = Context.trim_oldest_memories(memories)
    assert removed == 1
    assert "Lydia 1." not in trimmed and "Lydia 2." in trimmed and "Ralof 1." in trimmed
    assert trimmed.count("[This is the") == 4
    assert Context.trim_oldest_memories(trimmed) == (trimmed, 0)


def test_claude_cache_breakpoints():
    from src.llm.claude_cache_connector import ClaudeCacheConnector
    connector = ClaudeCacheConnector()
    messages = [
        {"role": "system", "content": "You are Ralof."},
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hail."},
        {"role": "user", "content": "Where are we?"},
    ]
    transformed = connector.transform_messages(messages)
    assert transformed[0]["content"][-1]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}
    assert transformed[2]["content"][-1]["cache_control"] == {"type": "ephemeral", "ttl": "5m"} # everything before the newest message
    assert transformed[1]["content"] == "Hello" and transformed[3]["content"] == "Where are we?"
    assert messages[0]["content"] == "You are Ralof." # the original messages are not modified

    first_turn = connector.transform_messages(messages[:2])
    assert first_turn[0]["content"][-1]["cache_control"]["ttl"] == "1h"
    assert first_turn[1]["content"] == "Hello"


def test_console_log_file(tmp_path):
    import logging
    from src.ui.log_buffer import ConsoleLogFile
    logger = logging.getLogger("test_console_log_file")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    console_log = ConsoleLogFile()

    assert console_log.apply_setting(False, str(tmp_path), logger) is None
    assert not (tmp_path / "logs").exists()

    file_path = console_log.apply_setting(True, str(tmp_path), logger)
    logger.info("saved line")
    console_log.apply_setting(False, str(tmp_path), logger)
    logger.info("not saved")

    assert file_path and file_path.startswith(str(tmp_path / "logs"))
    content = open(file_path, encoding="utf-8").read()
    assert "saved line" in content and "not saved" not in content


def test_xtts_url_local():
    assert TTSDefinitions.is_xtts_url_local("http://127.0.0.1:8020")
    assert not TTSDefinitions.is_xtts_url_local("http://192.168.1.50:8020")


def test_skyrim_game_screenshot(tmp_path, monkeypatch):
    import cv2
    import src.image.image_manager as image_manager_module
    from src.config.definitions.game_definitions import GameEnum

    monkeypatch.setattr(image_manager_module.platform, "system", lambda: "Linux") # skip Windows-only setup
    manager = ImageManager(GameEnum.SKYRIM, str(tmp_path), False, 80, False, "Nearest", {}, True, str(tmp_path))
    (tmp_path / "ScreenShot0.png").write_bytes(b"an older screenshot of the player") # must be left alone

    def press_key():
        cv2.imwrite(str(tmp_path / "ScreenShot1.png"), np.full((90, 160, 3), 120, dtype=np.uint8))
    monkeypatch.setattr(manager, "_press_screenshot_key", press_key)

    screenshot, width, height = manager._take_skyrim_screenshot(timeout=1.0)
    assert (width, height) == (160, 90)
    assert screenshot.shape == (90, 160, 3)
    assert not (tmp_path / "ScreenShot1.png").exists() # removed after reading
    assert (tmp_path / "ScreenShot0.png").exists()

    # no screenshot appears: no image, no crash
    monkeypatch.setattr(manager, "_press_screenshot_key", lambda: None)
    assert manager._take_skyrim_screenshot(timeout=0.2) is None


def test_waiting_for_speech_can_be_cancelled():
    """A request that waits for the player to speak can be called off (eg to end the conversation while push-to-talk is idle)"""
    import threading
    import pytest
    from src.stt.stt import Transcriber, ListeningCancelled

    transcriber = Transcriber.__new__(Transcriber) # only the state used by get_latest_transcription is set up
    transcriber._transcription_ready = threading.Event()
    transcriber._cancel_waiting = threading.Event()
    transcriber._lock = threading.Lock()
    transcriber._current_transcription = ''
    transcriber._speech_detected = False

    threading.Timer(0.1, transcriber.cancel_waiting).start()
    with pytest.raises(ListeningCancelled):
        transcriber.get_latest_transcription.__wrapped__(transcriber) if hasattr(transcriber.get_latest_transcription, '__wrapped__') else transcriber.get_latest_transcription()

    transcriber.clear_cancel_waiting()
    assert not transcriber._cancel_waiting.is_set()
    assert not transcriber._transcription_ready.is_set()


def _make_idle_transcriber(key_pressed: bool):
    import threading
    from src.stt.stt import Transcriber

    class FakeKey:
        def __init__(self, pressed): self.pressed = pressed
        def is_pressed(self): return self.pressed

    transcriber = Transcriber.__new__(Transcriber)
    transcriber._idle_lock = threading.Lock()
    transcriber._lock = threading.Lock()
    transcriber._preroll = np.array([], dtype=np.float32)
    transcriber._preroll_time = 0
    transcriber._use_preroll = False
    transcriber._ptt = FakeKey(key_pressed)
    transcriber._audio_buffer = np.array([], dtype=np.float32)
    transcriber._ptt_active = False
    transcriber._speech_detected = False
    transcriber._last_update_time = 0
    transcriber.listen_timeout = 30
    transcriber.loglevel = 27
    transcriber.finalized = []
    transcriber._finalize_transcription = lambda **kwargs: transcriber.finalized.append(len(transcriber._audio_buffer))
    return transcriber


def test_speech_before_conversation_start_is_continued_while_key_is_held():
    transcriber = _make_idle_transcriber(key_pressed=True)
    one_second = np.ones(transcriber.SAMPLING_RATE, dtype=np.float32)
    transcriber._add_to_preroll(one_second, is_new_press=True)
    transcriber._add_to_preroll(one_second, is_new_press=False)

    transcriber.use_idle_capture_for_next_listen(True)
    transcriber._apply_preroll()
    assert len(transcriber._audio_buffer) == 2 * transcriber.SAMPLING_RATE
    assert transcriber._ptt_active and transcriber._speech_detected
    assert transcriber.finalized == [] # transcribed once the key is released
    assert len(transcriber._preroll) == 0


def test_speech_before_conversation_start_is_transcribed_if_key_was_released():
    transcriber = _make_idle_transcriber(key_pressed=False)
    transcriber._add_to_preroll(np.ones(transcriber.SAMPLING_RATE, dtype=np.float32), is_new_press=True)
    transcriber.use_idle_capture_for_next_listen(True)
    transcriber._apply_preroll()
    assert transcriber.finalized == [transcriber.SAMPLING_RATE]


def test_speech_before_conversation_start_is_ignored_unless_meant_for_it():
    transcriber = _make_idle_transcriber(key_pressed=False)
    transcriber._add_to_preroll(np.ones(transcriber.SAMPLING_RATE, dtype=np.float32), is_new_press=True)
    transcriber.use_idle_capture_for_next_listen(False) # conversation started another way
    transcriber._apply_preroll()
    assert transcriber.finalized == [] and len(transcriber._audio_buffer) == 0

    # a new key press replaces what was recorded on the previous one
    transcriber._add_to_preroll(np.ones(100, dtype=np.float32), is_new_press=True)
    transcriber._add_to_preroll(np.ones(50, dtype=np.float32), is_new_press=True)
    assert len(transcriber._preroll) == 50
