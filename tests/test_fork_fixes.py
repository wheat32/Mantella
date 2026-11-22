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
