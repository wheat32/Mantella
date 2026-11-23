import os
import pytest
import src.wine as wine


@pytest.fixture(autouse=True)
def clear_wine_cache():
    wine.is_running_under_wine.cache_clear()
    yield
    wine.is_running_under_wine.cache_clear()


def test_not_under_wine_on_other_platforms(monkeypatch):
    monkeypatch.setattr(wine.platform, "system", lambda: "Linux")
    assert wine.is_running_under_wine() is False
    assert wine.apply_wine_workarounds() is False
    assert wine.disable_hugging_face_symlinks() is False


def test_workarounds_keep_user_defined_values(monkeypatch):
    monkeypatch.setattr(wine, "is_running_under_wine", lambda: True)
    monkeypatch.setenv("KMP_AFFINITY", "compact")
    monkeypatch.delenv("KMP_TOPOLOGY_METHOD", raising=False)

    assert wine.apply_wine_workarounds() is True
    assert os.environ["KMP_TOPOLOGY_METHOD"] == "flat"
    assert os.environ["KMP_AFFINITY"] == "compact" # values set by the user are not overwritten


def test_workarounds_not_applied_outside_wine(monkeypatch):
    monkeypatch.setattr(wine, "is_running_under_wine", lambda: False)
    monkeypatch.delenv("KMP_TOPOLOGY_METHOD", raising=False)

    assert wine.apply_wine_workarounds() is False
    assert "KMP_TOPOLOGY_METHOD" not in os.environ


def test_hugging_face_symlinks_disabled_under_wine(monkeypatch):
    from huggingface_hub import file_download
    monkeypatch.setattr(wine, "is_running_under_wine", lambda: True)
    monkeypatch.setattr(file_download, "are_symlinks_supported", file_download.are_symlinks_supported)

    assert wine.disable_hugging_face_symlinks() is True
    assert file_download.are_symlinks_supported("any folder") is False


def test_paths_are_unchanged_outside_wine(monkeypatch):
    monkeypatch.setattr(wine, "is_running_under_wine", lambda: False)
    assert wine.to_host_path("C:\\users\\steamuser\\Documents") == "C:\\users\\steamuser\\Documents"
    assert wine.to_windows_path("/home/user/Games") == "/home/user/Games"


def test_only_absolute_host_paths_are_converted(monkeypatch):
    monkeypatch.setattr(wine, "is_running_under_wine", lambda: True)
    # no conversion is attempted (and so no Windows API is needed) for paths that are already Windows paths
    assert wine.to_windows_path("C:\\Games\\Piper") == "C:\\Games\\Piper"
    assert wine.to_windows_path("") == ""


def test_same_windows_path():
    assert wine._is_same_windows_path("Z:\\mnt\\games\\Skyrim\\data", "z:/mnt/games/Skyrim/Data\\")
    # a path in a mod manager's virtual folder converts to somewhere else (eg its overwrite folder)
    assert not wine._is_same_windows_path("Z:\\mnt\\mo2\\overwrite\\SKSE", "Z:\\mnt\\games\\Skyrim\\data\\SKSE")
