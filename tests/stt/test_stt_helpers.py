import os
import pytest
from src.stt import stt
from src.stt.stt import correct_names_in_transcript, find_empty_files, raise_if_model_files_empty, remove_empty_cached_model_files


@pytest.mark.parametrize("transcript, names, expected", [
    ("Hello roll off, how are you?", ["Ralof"], "Hello Ralof, how are you?"),
    ("Where is Rolof.", ["Ralof"], "Where is Ralof."),
    ("I spoke with lidia yesterday.", ["Lydia"], "I spoke with Lydia yesterday."),
    ("That is Ralof's axe.", ["Ralof"], "That is Ralof's axe."),
    ("Have you seen all frick?", ["Ulfric Stormcloak"], "Have you seen Ulfric?"),
    ("Have you seen Ulfrick?", ["Ulfric Stormcloak"], "Have you seen Ulfric?"),
    ("Tell me about the storm cloak rebellion.", ["Ulfric Stormcloak"], "Tell me about the Stormcloak rebellion."),
])
def test_correct_names_in_transcript(transcript, names, expected):
    assert correct_names_in_transcript(transcript, names) == expected


@pytest.mark.parametrize("transcript", [
    "I need some relief from this cold.",
    "The wolf ran off. We should follow it.",
    "Let me roll the dice.",
    "Hello there, how are you today?",
    "",
])
def test_ordinary_words_are_not_replaced_with_names(transcript):
    assert correct_names_in_transcript(transcript, ["Ralof", "Lydia", "Hadvar"]) == transcript


def test_correct_names_without_names():
    assert correct_names_in_transcript("Hello roll off.", []) == "Hello roll off."
    assert correct_names_in_transcript("Hello roll off.", ["Jon"]) == "Hello roll off." # names this short are too easily confused with words


def test_words_are_not_merged_across_sentences():
    assert correct_names_in_transcript("I took a roll. Off we go.", ["Ralof"]) == "I took a roll. Off we go."


def test_find_empty_files(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "model.bin").write_bytes(b"data")
    (tmp_path / "sub" / "encoder_model.onnx").write_bytes(b"")

    assert find_empty_files(str(tmp_path)) == [os.path.join(str(tmp_path), "sub", "encoder_model.onnx")]
    assert find_empty_files(str(tmp_path / "missing")) == []


def test_raise_if_model_files_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(stt.utils, "play_error_sound", lambda: None)
    (tmp_path / "decoder_model_merged.onnx").write_bytes(b"data")
    raise_if_model_files_empty(str(tmp_path), "moonshine/tiny") # does not raise

    (tmp_path / "encoder_model.onnx").write_bytes(b"")
    with pytest.raises(FileNotFoundError, match="encoder_model.onnx"):
        raise_if_model_files_empty(str(tmp_path), "moonshine/tiny")


def test_remove_empty_cached_model_files(tmp_path, monkeypatch):
    cache_folder = tmp_path / "models--UsefulSensors--moonshine"
    snapshot = cache_folder / "snapshots" / "abc"
    snapshot.mkdir(parents=True)
    (snapshot / "encoder_model.onnx").write_bytes(b"")
    (snapshot / "decoder_model_merged.onnx").write_bytes(b"data")
    monkeypatch.setattr(stt, "get_hugging_face_model_cache_folder", lambda repo_id: str(cache_folder))

    assert remove_empty_cached_model_files("UsefulSensors/moonshine") == 1
    assert not (snapshot / "encoder_model.onnx").exists()
    assert (snapshot / "decoder_model_merged.onnx").exists()
    assert remove_empty_cached_model_files(None) == 0
