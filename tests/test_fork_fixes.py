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


def test_waiting_for_speech_can_be_canceled():
    """A request that waits for the player to speak can be called off (eg to end the conversation while push-to-talk is idle)"""
    import threading
    import pytest
    from src.stt.stt import Transcriber, ListeningCanceled

    transcriber = Transcriber.__new__(Transcriber) # only the state used by get_latest_transcription is set up
    transcriber._transcription_ready = threading.Event()
    transcriber._cancel_waiting = threading.Event()
    transcriber._lock = threading.Lock()
    transcriber._current_transcription = ''
    transcriber._speech_detected = False

    threading.Timer(0.1, transcriber.cancel_waiting).start()
    with pytest.raises(ListeningCanceled):
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


def test_console_log_limits_and_delete(tmp_path):
    import logging
    from src.ui.log_buffer import ConsoleLogFile
    logger = logging.getLogger("test_console_log_limits")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logs_folder = tmp_path / "logs"
    logs_folder.mkdir()
    for day in range(1, 6): # logs of five earlier runs, one of them in two parts
        (logs_folder / f"console_2026010{day}_120000.log").write_text("old run", encoding="utf-8")
    (logs_folder / "console_20260101_120000.log.1").write_text("old run, first part", encoding="utf-8")
    (logs_folder / "notes.txt").write_text("not a console log", encoding="utf-8")

    console_log = ConsoleLogFile()
    file_path = console_log.apply_setting(True, str(tmp_path), logger, max_size_mb=1, max_files=3)
    remaining = sorted(f.name for f in logs_folder.iterdir())
    # the current run and the two newest earlier runs are kept
    assert remaining == ["console_20260104_120000.log", "console_20260105_120000.log", file_path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1], "notes.txt"]

    # a run's log never takes up more than twice the size limit
    for _ in range(40):
        logger.info("x" * 100_000)
    sizes = [f.stat().st_size for f in logs_folder.iterdir() if f.name.startswith(file_path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1])]
    assert len(sizes) == 2 and all(size <= 1024 * 1024 + 200_000 for size in sizes)

    deleted = console_log.delete_saved_logs(str(tmp_path), logger)
    assert deleted == 4
    logger.info("after delete")
    console_log.apply_setting(False, str(tmp_path), logger)
    # saving carries on in a fresh file, and other files in the folder are left alone
    assert sorted(f.name for f in logs_folder.iterdir()) == [file_path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1], "notes.txt"]
    assert "after delete" in open(file_path, encoding="utf-8").read()


def test_free_flow_conversation_has_no_greeting(default_conversation):
    """A conversation the player started by speaking waits for the player, instead of having the NPC answer an automatic greeting"""
    from src.http.communication_constants import communication_constants as comm_consts
    assert default_conversation.context.config.automatic_greeting
    default_conversation.update_context('Whiterun', 12, None, None, None, None, None) # sets up the system message, as a start request does
    assert len(default_conversation._Conversation__messages) == 1

    reply_type, _ = default_conversation.start_conversation(player_speaks_first=True)
    assert reply_type == comm_consts.KEY_REPLYTYPE_PLAYERTALK

    # The game asks what happens next: this must hand over to the player, not generate a greeting
    reply_type, sentence = default_conversation.continue_conversation()
    assert reply_type == comm_consts.KEY_REPLYTYPE_PLAYERTALK
    assert sentence is None
    assert len(default_conversation._Conversation__messages) == 1 # only the system message


def test_xtts_url_check(monkeypatch):
    import requests
    from src.ui import connection_tests

    class Response:
        def __init__(self, status_code, body):
            self.status_code = status_code
            self._body = body
        def json(self):
            if isinstance(self._body, Exception):
                raise self._body
            return self._body

    def fake_server(url, timeout):
        if url.endswith('/speakers_list'):
            return Response(200, {'en': {'speakers': ['maleeventoned', 'femalenord']}, 'de': {'speakers': ['malenord']}})
        return Response(200, ['v2.0.2', 'main'])
    monkeypatch.setattr(connection_tests.requests, 'get', fake_server)
    is_success, message = connection_tests.check_xtts_url(' http://127.0.0.1:8020/ ')
    assert is_success
    assert 'http://127.0.0.1:8020:' in message and '3 voice(s) in 2 language(s)' in message and '2 model(s)' in message

    def refuse(url, timeout):
        raise requests.exceptions.ConnectionError()
    monkeypatch.setattr(connection_tests.requests, 'get', refuse)
    is_success, message = connection_tests.check_xtts_url('http://127.0.0.1:8020')
    assert not is_success and 'Could not connect' in message

    monkeypatch.setattr(connection_tests.requests, 'get', lambda url, timeout: Response(404, None))
    assert not connection_tests.check_xtts_url('http://127.0.0.1:8020')[0]
    monkeypatch.setattr(connection_tests.requests, 'get', lambda url, timeout: Response(200, ValueError('not json')))
    assert not connection_tests.check_xtts_url('http://127.0.0.1:8020')[0]

    assert not connection_tests.check_xtts_url('')[0]
    assert not connection_tests.check_xtts_url('127.0.0.1:8020')[0]


def test_push_to_talk_key_is_reported_to_the_game():
    """The game binds its free-flow talk key to the code of the push-to-talk key"""
    from src.stt.ptt_controller import PTTController
    assert PTTController.get_game_key_code('V') == 47
    assert PTTController.get_game_key_code(' v ') == 47
    assert PTTController.get_game_key_code('H') == 35 # same code as the mod's default text prompt key
    assert PTTController.get_game_key_code('space') == 57
    assert PTTController.get_game_key_code('F12') == 88
    assert PTTController.get_game_key_code('') is None
    assert PTTController.get_game_key_code('not a key') is None
    # every key that push-to-talk accepts (apart from F13-F24) is known to the game as well
    for key in list(PTTController._SPECIAL_KEYS) + [chr(c) for c in range(ord('A'), ord('Z') + 1)] + [str(d) for d in range(10)] + [f'F{n}' for n in range(1, 13)]:
        assert PTTController.get_game_key_code(key) is not None, key


def test_numbered_duplicate_is_found_in_character_list(skyrim):
    """ "Bandit 2" (numbered by the game, as two bandits are in the conversation) gets the same background as "Bandit" """
    info, is_generic = skyrim.find_character_info('0977F5', 'bandit', 'Nord', 1, 'FemaleNord')
    assert not is_generic
    numbered_info, numbered_is_generic = skyrim.find_character_info('0977F7', 'bandit 2', 'Nord', 1, 'FemaleNord')
    assert not numbered_is_generic
    assert numbered_info['bio'] == info['bio']


def test_numbered_names_are_explained_to_the_llm():
    from src.conversation.context import Context
    assert Context.get_numbered_names_note(['Ralof', 'Gerdur']) == ''
    note = Context.get_numbered_names_note(['bandit', 'bandit 2', 'Ralof'])
    assert 'bandit 2' in note and 'Ralof' not in note


def test_push_to_talk_key_is_taken_from_the_game(tmp_path):
    """The push-to-talk key is set in the game's mod menu, reported by its key code and remembered between runs"""
    from src.stt.ptt_controller import PTTController
    assert PTTController.get_key_name(47) == 'V'
    assert PTTController.get_key_name(57) == 'SPACE'
    assert PTTController.get_key_name(259) == 'MOUSE4'
    assert PTTController.get_key_name(51) == 'SC51' # a key without a name of its own is kept as its scan code
    assert PTTController.get_game_key_code('SC51') == 51
    for not_a_key in (None, -1, 0, True, 'V', 9999):
        assert PTTController.get_key_name(not_a_key) is None
    assert PTTController._normalize_key_to_vk('MOUSE4') == 0x05

    # nothing reported by the game yet: the defaults apply
    assert PTTController.load_saved_settings(str(tmp_path), False, 'V') == (False, 'V')
    assert PTTController.load_saved_settings(str(tmp_path), True, 'SPACE') == (True, 'SPACE')
    PTTController.save_settings(str(tmp_path), True, 'MOUSE4')
    assert PTTController.load_saved_settings(str(tmp_path), False, 'V') == (True, 'MOUSE4')
    PTTController.save_settings(str(tmp_path), False, 'MOUSE4')
    assert PTTController.load_saved_settings(str(tmp_path), True, 'V') == (False, 'MOUSE4')
    (tmp_path / PTTController.SAVED_SETTINGS_FILE_NAME).write_text('nonsense')
    assert PTTController.load_saved_settings(str(tmp_path), False, 'V') == (False, 'V')
    (tmp_path / PTTController.SAVED_SETTINGS_FILE_NAME).write_text('{"enabled": "yes", "key": "not a key"}')
    assert PTTController.load_saved_settings(str(tmp_path), False, 'V') == (False, 'V')


def test_push_to_talk_can_be_switched_by_the_game():
    """The game reports whether push-to-talk is on: the listener follows, except while the microphone is in use"""
    from src.stt.ptt_controller import PTTController
    transcriber = _make_idle_transcriber(key_pressed=False)
    transcriber._ptt = PTTController('V')
    transcriber.ptt_enabled = True
    started, stopped = [], []
    transcriber.start_idle_capture = lambda: started.append(True)
    transcriber.stop_idle_capture = lambda: stopped.append(True)
    transcriber._running = False

    transcriber.set_push_to_talk(False, 'V')
    assert transcriber.ptt_enabled is False and stopped and transcriber._ptt._vk is None

    transcriber.set_push_to_talk(True, 'SPACE')
    assert transcriber.ptt_enabled is True and started and transcriber._ptt._vk == 0x20

    transcriber._running = True
    transcriber.set_push_to_talk(False, 'SPACE')
    assert transcriber.ptt_enabled is True # left for later


def _write_frame_like_the_plugin(path, width: int, height: int, top_row_bgr, other_rows_bgr):
    """Writes a .bmp the way skse/SKSE_HTTP/src/FrameCapture.cpp does: 24 bit, rows from bottom to top, rows padded to 4 bytes"""
    import struct
    row_size = width * 3
    padding = (4 - row_size % 4) % 4
    data_size = (row_size + padding) * height
    header_size = 14 + 40
    rows = [bytes(top_row_bgr) * width] + [bytes(other_rows_bgr) * width] * (height - 1) # from top to bottom
    with open(path, 'wb') as f:
        f.write(struct.pack('<HIII', 0x4D42, header_size + data_size, 0, header_size))
        f.write(struct.pack('<IiiHHIIiiII', 40, width, height, 1, 24, 0, data_size, 0, 0, 0, 0))
        for row in reversed(rows):
            f.write(row + b'\x00' * padding)


def test_skyrim_frame_capture(tmp_path, monkeypatch):
    """Experimental fast game screenshots: the frame saved by the SKSE plugin is picked up, and anything going wrong means "not captured" """
    import src.image.image_manager as image_manager_module
    from src.config.definitions.game_definitions import GameEnum

    monkeypatch.setattr(image_manager_module.platform, "system", lambda: "Linux") # skip Windows-only setup
    manager = ImageManager(GameEnum.SKYRIM, str(tmp_path), False, 80, False, "Nearest", {}, True, str(tmp_path), True)
    frame_folder = tmp_path / 'data' / 'tmp'
    frame_folder.mkdir(parents=True)
    frame_path = frame_folder / ImageManager.FRAME_CAPTURE_FILE_NAME

    def plugin_saves_frame():
        _write_frame_like_the_plugin(frame_path, 5, 3, top_row_bgr=(255, 0, 0), other_rows_bgr=(0, 0, 200)) # a width that needs padding
        return True
    monkeypatch.setattr(manager, "_request_frame_capture", plugin_saves_frame)
    frame, width, height = manager._capture_skyrim_frame(timeout=1.0)
    assert (width, height) == (5, 3)
    assert tuple(frame[0, 0]) == (255, 0, 0) and tuple(frame[0, 4]) == (255, 0, 0) # the top row stays on top
    assert tuple(frame[2, 2]) == (0, 0, 200)
    assert not frame_path.exists() # removed after reading

    # the plugin cannot be reached, saves nothing, or saves a black frame
    monkeypatch.setattr(manager, "_request_frame_capture", lambda: False)
    assert manager._capture_skyrim_frame(timeout=0.2) is None
    monkeypatch.setattr(manager, "_request_frame_capture", lambda: True)
    assert manager._capture_skyrim_frame(timeout=0.2) is None
    def plugin_saves_black_frame():
        _write_frame_like_the_plugin(frame_path, 8, 4, top_row_bgr=(0, 0, 0), other_rows_bgr=(0, 0, 0))
        return True
    monkeypatch.setattr(manager, "_request_frame_capture", plugin_saves_black_frame)
    assert manager._capture_skyrim_frame(timeout=1.0) is None


def test_notable_items_are_described_in_the_prompt():
    """Notable things an NPC carries (reported by the game) are passed on to the LLM, as something that may come up"""
    from src.conversation.context import Context
    assert Context.get_notable_items_description('bandit', None) == ''
    assert Context.get_notable_items_description('bandit', []) == ''
    assert Context.get_notable_items_description('bandit', 'not a list') == ''
    description = Context.get_notable_items_description('bandit', ['250 gold', 'Treasure Map I (Map to a hidden treasure near Riverwood)', ' '])
    assert description.startswith('bandit carries: 250 gold, Treasure Map I (Map to a hidden treasure near Riverwood).')


def test_system_information_printed_at_startup(tmp_path, monkeypatch):
    import os
    import src.system_info as system_info
    from src.config.definitions.game_definitions import GameEnum

    # the version is read from the file itself: signature, structure version, then the version as two 32 bit numbers
    program = tmp_path / 'program.exe'
    program.write_bytes(b'MZ' + b'\x00' * 100 + bytes.fromhex('BD04EFFE') + bytes.fromhex('00000100') + bytes.fromhex('07000100') + bytes.fromhex('00006800') + b'\x00' * 20)
    assert system_info.get_file_version(str(program)) == '1.7.104.0'
    (tmp_path / 'no_version.exe').write_bytes(b'MZ' + b'\x00' * 100)
    assert system_info.get_file_version(str(tmp_path / 'no_version.exe')) is None
    assert system_info.get_file_version(str(tmp_path / 'missing.exe')) is None

    assert system_info.format_script_extender_version('0.2.2.6') == '2.2.6'
    assert system_info.format_script_extender_version('1.7.104.0') == '1.7.104.0'
    assert system_info.format_script_extender_version(None) is None
    assert system_info.parse_os_release('NAME="Arch Linux"\nPRETTY_NAME="Arch Linux"\nID=arch\n') == 'Arch Linux'
    assert system_info.parse_os_release('ID=arch\n') is None

    # the game folder is not known
    lines = dict(system_info.get_game_details(GameEnum.SKYRIM, None))
    assert lines['Game'] == 'Skyrim' and 'unknown' in lines['Game version'] and lines['SKSE version'] == 'unknown'

    # versions are read from the files in the game folder
    for name in ('SkyrimSE.exe', 'skse64_1_7_104.dll', 'skse64_steam_loader.dll', 'skse64_loader.exe'):
        (tmp_path / name).write_bytes(b'')
    versions = {'SkyrimSE.exe': '1.7.104.0', 'skse64_1_7_104.dll': '0.2.3.1'}
    monkeypatch.setattr(system_info, 'get_file_version', lambda path: versions.get(os.path.basename(path)))
    details = system_info.get_game_details(GameEnum.SKYRIM, str(tmp_path))
    assert ('Game version', '1.7.104.0') in details
    assert ('SKSE version', '2.3.1 (skse64_1_7_104.dll)') in details
    assert len(details) == 3 # the loaders are not listed as the script extender

    info = system_info.get_system_info('0.17.0-alpha.1', GameEnum.SKYRIM, str(tmp_path), True)
    labels = [label for label, _ in info]
    for expected in ('Mantella version', 'Python version', 'OS', 'CPU arch', 'Game version', 'SKSE version', 'Started by'):
        assert expected in labels
    printed = system_info.format_system_info(info)
    assert printed[0] == '=== Mantella starting ===' and set(printed[-1]) == {'='}
    assert len({line.index(' : ') for line in printed[1:-1]}) == 1 # the values line up


def test_interruptions_are_told_apart():
    """Speaking as the NPC finishes a line is not talking over them, and only cutting into a line is described as such"""
    from src.conversation.conversation import Conversation
    kind = Conversation.get_interruption_kind
    # the line started at 100 and lasts 5 seconds
    assert kind(101.0, 101.2, 100.0, 5.0, True, 1.0) == 'mid_line'
    assert kind(104.5, 105.0, 100.0, 5.0, True, 1.0) == 'between_lines' # within the last second: practically finished
    assert kind(106.0, 106.1, 100.0, 5.0, True, 1.0) == 'between_lines' # in the pause before the next line
    assert kind(106.0, 106.1, 100.0, 5.0, False, 1.0) is None # the NPC had nothing more to say
    assert kind(None, 101.0, 100.0, 5.0, True, 1.0) == 'mid_line' # without a start time, the moment it was noticed counts

    text = Conversation.get_interruption_event_text
    assert text('Nick', 'Fisherman', None) == ''
    assert 'cut in while Fisherman was still speaking' in text('Nick', 'Fisherman', 'mid_line')
    assert 'interrupted' not in text('Nick', 'Fisherman', 'between_lines') and 'left the rest unsaid' in text('Nick', 'Fisherman', 'between_lines')


def test_unplayed_sentence_is_taken_back(default_config, example_skyrim_npc_character):
    """A line that was never played because the player spoke first is not part of what the NPC said"""
    from src.llm.messages import AssistantMessage
    from src.llm.message_thread import message_thread
    from src.llm.sentence import Sentence
    from src.llm.sentence_content import SentenceContent, SentenceTypeEnum
    thread = message_thread(default_config, "system")
    message = AssistantMessage(default_config)
    thread.add_message(message)
    played = Sentence(SentenceContent(example_skyrim_npc_character, "I didn't know it.", SentenceTypeEnum.SPEECH), "", 1.0)
    unplayed = Sentence(SentenceContent(example_skyrim_npc_character, "You said Nick, didn't you?", SentenceTypeEnum.SPEECH), "", 1.0)
    message.add_sentence(played)
    message.add_sentence(unplayed)
    assert message.remove_sentence(unplayed)
    assert "Nick" not in message.get_formatted_content() and message.sentence_count == 1
    assert not message.remove_sentence(unplayed)
    assert thread.remove_message(message) and len(thread) == 1
    assert not thread.remove_message(thread[0]) # the system message stays


def test_what_npcs_carry_and_who_knows_the_player():
    from src.conversation.context import Context
    from src.remember.summaries import Summaries
    description = Context.get_notable_items_description('Fisherman', None, ['food', 'odds and ends'])
    assert 'food, odds and ends' in description and 'does not make up others' in description
    nothing = Context.get_notable_items_description('Fisherman', [], None, True)
    assert 'nothing to give' in nothing
    assert Context.get_notable_items_description('Fisherman', None, None, None) == ''

    note = Context.get_unknown_player_name_note('Nick', ['Fisherman'])
    assert "Fisherman only does if Nick has told it" in note and "a courier sent to find Nick" in note
    assert Context.get_unknown_player_name_note('Nick', []) == ''
    relationships = Context.get_relationships_note('Nick', [('Nazeem', 'a stranger'), ('Lydia', 'a friend')])
    assert 'to Nazeem, Nick is someone Nazeem has just met and to Lydia, Nick is a friend' in relationships
    assert "'Stranger' is fine now and then, but they vary it" in note
    assert "'the stranger'" in Summaries.get_unknown_player_name_summary_note('Nick', ['Fisherman'])
    assert 'Only use the name Nick' in Summaries.get_unknown_player_name_summary_note('Nick', ['Fisherman'])
    assert Summaries.get_unknown_player_name_summary_note('Nick', []) == ''


def test_actions_at_the_end_of_a_response(example_skyrim_npc_character):
    """A lone "Inventory:" at the end is not lost, and actions that open a menu wait for the NPC to finish"""
    from src.llm.output.actions_parser import actions_parser
    from src.llm.output.output_parser import sentence_generation_settings
    from src.llm.output.sentence_accumulator import sentence_accumulator
    from src.llm.sentence_content import SentenceContent, SentenceTypeEnum
    from src.conversation.action import Action
    def make_action(identifier, keyword):
        return Action(identifier=identifier, name=keyword, keyword=keyword, description="", prompt_text="", requires_response=False,
                      is_interrupting=False, one_on_one=True, multi_npc=True, radiant=True)
    parser = actions_parser([make_action('mantella_npc_inventory', 'Inventory'), make_action('mantella_npc_follow', 'Follow')])
    settings = sentence_generation_settings(example_skyrim_npc_character)

    text, found = parser.find_actions_in_text("\n\ninventory :")
    assert text == '' and [a.identifier for a in found] == ['mantella_npc_inventory']

    sentence = SentenceContent(example_skyrim_npc_character, "Inventory: Right, let's see.", SentenceTypeEnum.SPEECH)
    parsed, _ = parser.modify_sentence_content(sentence, None, settings)
    assert parsed.text == "Right, let's see." and parsed.actions == [] # waits for the end of the response
    assert settings.deferred_actions == [{'identifier': 'mantella_npc_inventory'}]
    sentence = SentenceContent(example_skyrim_npc_character, "Follow: Lead the way.", SentenceTypeEnum.SPEECH)
    parsed, _ = parser.modify_sentence_content(sentence, None, settings)
    assert parsed.actions == [{'identifier': 'mantella_npc_follow'}] # other actions happen right away

    accumulator = sentence_accumulator(['.', '?', '!', ':'])
    accumulator.accumulate("Take a look.\n\nInventory:")
    assert accumulator.has_next_sentence()
    accumulator.get_next_sentence()
    assert 'Inventory:' in accumulator.take_remaining_text()
    assert accumulator.take_remaining_text() == ''


def test_conversation_from_a_game_that_was_left_is_not_remembered(default_conversation, monkeypatch):
    """Loading a save during a conversation: the conversation belongs to the game that was left, and is not added to memories"""
    from src.game_manager import GameStateManager
    other = GameStateManager.is_from_another_play_session
    assert other(1234, 5678)
    assert not other(1234, 1234)
    assert not other(None, 5678) # older versions of the mod send no number
    assert not other(1234, None)
    assert not other(True, 5)

    saved = []
    monkeypatch.setattr(default_conversation, '_Conversation__save_conversation', lambda **kwargs: saved.append(kwargs))
    default_conversation.end(remember=False)
    assert saved == []
    default_conversation.end()
    assert len(saved) == 1


def test_proton_details_are_read_from_the_prefix(tmp_path, monkeypatch):
    import src.system_info as system_info
    (tmp_path / 'version').write_text('11.0-100\n')
    (tmp_path / 'config_info').write_text('11.0-100\n/mnt/games/SteamLibrary/steamapps/common/Proton 11.0/files/share/fonts/\n')
    monkeypatch.setenv('STEAM_COMPAT_DATA_PATH', str(tmp_path))
    monkeypatch.setattr(system_info, '_to_wine_path', lambda host_path: host_path) # read directly, as this test does not run under Wine
    assert system_info._get_proton_version() == 'Proton 11.0 (11.0-100)'
    monkeypatch.delenv('STEAM_COMPAT_DATA_PATH')
    assert system_info._get_proton_version() is None


def test_role_names_and_event_cleanup():
    from src.conversation.context import Context
    note = Context.get_role_names_note(['Fisherman'])
    assert 'Fisherman is only what people call someone like them' in note and 'never introduce themselves as Fisherman' in note
    assert Context.get_role_names_note([]) == ''

    events = Context.clean_ingame_events([
        'Nick: Hello; Vigilant of Stendarr: You speak to a Vigilant of Stendarr.',
        'Nick: Hello;\n Vigilant of Stendarr: You speak to a Vigilant of Stendarr.', # the same line, reported again
        'Nick: Goodbye. (Remove from Mantella conversation); Fisherman: Goodbye', # an option of Mantella's own dialogue menu
        'Nick picked up / took Blue Dartwing',
    ])
    assert events == ['Nick: Hello; Vigilant of Stendarr: You speak to a Vigilant of Stendarr.',
                      'Nick: Goodbye.; Fisherman: Goodbye', # what was said is kept, the label of the option is not
                      'Nick picked up / took Blue Dartwing']


def test_a_sentence_ending_in_a_colon_is_not_a_character_change(example_skyrim_npc_character):
    from src.characters_manager import Characters
    from src.llm.output.change_character_parser import change_character_parser
    from src.llm.output.output_parser import sentence_generation_settings
    characters = Characters()
    characters.add_or_update_character(example_skyrim_npc_character)
    parser = change_character_parser(characters)
    settings = sentence_generation_settings(example_skyrim_npc_character)
    text = "We wander Tamriel hunting the abominations that prey on mortals:"
    assert parser.cut_sentence(text, settings) == (None, text)
    assert settings.stop_generation is False
    parser.cut_sentence("Hulda: Another round!", settings) # a short name of someone not in the conversation is still cut off
    assert settings.stop_generation is True


def test_walking_away_is_remembered():
    from src.conversation.conversation import Conversation
    text = Conversation.get_walked_away_event_text('Nick', ['Fisherman'])
    assert text.startswith('Nick walked away from Fisherman in the middle of the conversation') and 'personality' in text


def test_update_check_rules():
    """On a normal release only newer normal releases count; on a pre-release anything newer does"""
    from src.update_check import parse_version, find_newer_release
    order = ['0.15.3', '0.16.0', '0.17.0-alpha.1', '0.17.0-alpha.2', '0.17.0-alpha.10', '0.17.0-beta.1', '0.17.0-rc.1', '0.17.0', '0.17.1', '1.0.0']
    keys = [parse_version(v) for v in order]
    assert keys == sorted(keys) and len(set(keys)) == len(keys)
    assert parse_version('v0.17.0-alpha.3') == parse_version('0.17.0-alpha.3')
    assert parse_version('not a version') is None

    def release(tag, prerelease=False, draft=False):
        return {'tag_name': tag, 'prerelease': prerelease, 'draft': draft, 'html_url': f'https://github.com/wheat32/Mantella/releases/tag/{tag}'}
    releases = [release('v0.17.0-alpha.3', True), release('v0.17.0-alpha.2', True), release('v0.16.0'), release('v0.15.3'), release('v0.18.0', draft=True)]

    # on a normal release, a newer pre-release is not mentioned
    assert find_newer_release('0.16.0', releases) is None
    newer = find_newer_release('0.15.3', releases)
    assert newer.version == '0.16.0' and not newer.is_prerelease and newer.url.endswith('v0.16.0')
    # on a pre-release, any newer version is
    newer = find_newer_release('0.17.0-alpha.2', releases)
    assert newer.version == '0.17.0-alpha.3' and newer.is_prerelease
    assert find_newer_release('0.17.0-alpha.3', releases) is None
    assert find_newer_release('0.17.0-alpha.3', releases + [release('v0.17.0')]).version == '0.17.0'
    assert find_newer_release('unknown', releases) is None


def test_update_notice_text():
    from src.ui.start_ui import StartUI
    from src.update_check import NewRelease
    notice = StartUI.get_update_notice_html('0.16.0', NewRelease('0.17.0', 'https://github.com/wheat32/Mantella/releases/tag/v0.17.0', False))
    assert 'A new version of Mantella is available: <b>0.17.0</b> (this is 0.16.0)' in notice and 'releases/tag/v0.17.0' in notice
    assert 'new pre-release' in StartUI.get_update_notice_html('0.17.0-alpha.2', NewRelease('0.17.0-alpha.3', 'https://example.com', True))


def test_nearby_objects(example_skyrim_npc_character):
    """NPCs are told what is around them, and when that changes (but not when only distances do)"""
    from src.conversation.context import Context
    from src.http.communication_constants import communication_constants as comm_consts
    npc = example_skyrim_npc_character
    assert Context.get_nearby_objects(npc) is None # the game did not look (eg an older version of the mod)
    npc.set_custom_character_value(comm_consts.KEY_ACTOR_NEARBYOBJECTSCHECKED, True)
    assert Context.get_nearby_objects(npc) == []
    npc.set_custom_character_value(comm_consts.KEY_ACTOR_NEARBYOBJECTS, ['a burning campfire (3 m)', 'a tent (5 m)'])
    objects = Context.get_nearby_objects(npc)
    assert Context.get_nearby_objects_description('Fisherman', objects) == 'Notable things around Fisherman: a burning campfire (3 m), a tent (5 m).'
    assert Context.get_nearby_objects_description('Fisherman', []) == ''

    change = Context.get_nearby_objects_change_event
    assert change('Fisherman', objects, ['a burning campfire (4 m)', 'a tent (2 m)']) == '' # only closer or further away
    assert change('Fisherman', objects, ['a campfire that has gone out (3 m)', 'a tent (5 m)']) == 'Notable things around Fisherman now: a campfire that has gone out (3 m), a tent (5 m).'
    assert change('Fisherman', objects, []) == 'There is nothing of note around Fisherman anymore.'
    assert change('Fisherman', None, objects) == '' # nothing to compare with


def test_advanced_actions_follow_the_model():
    from src.config.definitions.action_definitions import ActionDefinitions as A
    assert A.resolve_advanced_actions('Automatic', 'Anthropic', 'claude-haiku-5-5')
    assert A.resolve_advanced_actions('Automatic', 'OpenRouter', 'anthropic/claude-sonnet-5.5')
    assert not A.resolve_advanced_actions('Automatic', 'OpenRouter', 'some-small/local-model')
    assert not A.resolve_advanced_actions('Automatic', 'KoboldCpp', 'anything')
    assert not A.resolve_advanced_actions('Off', 'Anthropic', 'claude-haiku-5-5')
    assert A.resolve_advanced_actions('On', 'KoboldCpp', 'anything')


def test_npc_records(tmp_path):
    from src.conversation.npc_records import NpcRecords
    assert NpcRecords.clean_name(' "Sariel". ') == 'Sariel'
    assert NpcRecords.clean_name('') == '' and NpcRecords.clean_name('1234') == '' and NpcRecords.clean_name('x' * 60) == ''

    world = tmp_path / 'Nick1'
    folder = world / 'Fisherman - 097977'
    folder.mkdir(parents=True)
    (folder / 'Fisherman.json').write_text('[]')
    (folder / 'Fisherman_summary_1.txt').write_text('Nick asked for some salmon.')

    records = NpcRecords(str(tmp_path), 'Nick1')
    assert records.get_given_name('097977') is None
    records.set_given_name('097977', 'Sariel')
    records.move_memories('097977', 'Fisherman', 'Sariel')
    assert (world / 'Sariel - 097977' / 'Sariel_summary_1.txt').read_text() == 'Nick asked for some salmon.'
    assert (world / 'Sariel - 097977' / 'Sariel.json').exists() and not folder.exists()

    records.set_companion('097977', 'traveling to Riverwood together', 'Riverwood')
    reloaded = NpcRecords(str(tmp_path), 'Nick1') # kept between runs
    assert reloaded.get_given_name('097977') == 'Sariel'
    assert reloaded.get_companion('097977') == {'purpose': 'traveling to Riverwood together', 'destination': 'Riverwood'}
    reloaded.remove_companion('097977')
    assert NpcRecords(str(tmp_path), 'Nick1').get_companion('097977') is None


def test_renaming_a_character(example_skyrim_npc_character):
    from src.characters_manager import Characters
    characters = Characters()
    characters.add_or_update_character(example_skyrim_npc_character)
    renamed = characters.rename_character('Guard', 'Sariel')
    assert renamed is example_skyrim_npc_character and renamed.name == 'Sariel'
    assert characters.contains_character('Sariel') and not characters.contains_character('Guard')
    assert characters.rename_character('Guard', 'Someone') is None


def test_belongings_and_companions_in_the_prompt():
    from src.conversation.context import Context
    from src.conversation.conversation import Conversation
    assert Context.get_owned_items_description('Sariel', ['Salmon Meat (3)', 'Fishing Rod']) == 'Belongs to Sariel nearby: Salmon Meat (3), Fishing Rod.'
    assert Context.get_owned_items_description('Sariel', None) == ''

    note = Context.get_companion_note('Nick', 'Sariel', 'traveling to Riverwood together.', 'Riverwood', 'Riverwood Trader')
    assert 'Sariel is traveling with Nick: traveling to Riverwood together.' in note and 'when they reach Riverwood' in note
    assert note.endswith('They have now reached Riverwood.')
    assert 'They have now reached' not in Context.get_companion_note('Nick', 'Sariel', 'traveling to Riverwood together', 'Riverwood', 'Skyrim')

    owned = ['Salmon Meat (3)', 'Fishing Rod', 'Septim Purse']
    assert Conversation.match_owned_items(['salmon'], owned) == ['Salmon Meat']
    assert Conversation.match_owned_items(['Salmon Meat (2)', 'Fishing Rod'], owned) == ['Salmon Meat', 'Fishing Rod']
    assert Conversation.match_owned_items(['Iron Sword'], owned) == [] # only what belongs to the NPC
