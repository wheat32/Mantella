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


def test_virtual_paths_are_written_the_way_the_host_writes_them(monkeypatch):
    """A path in a mod manager's virtual folder has no place of its own on the host. It is still shown without the Z: drive"""
    import ctypes
    import types
    monkeypatch.setattr(wine, "is_running_under_wine", lambda: True)
    monkeypatch.setattr(ctypes, "windll", types.SimpleNamespace(kernel32=None), raising=False)
    monkeypatch.setattr(wine.os.path, "abspath", lambda path: path)

    virtual_path = "Z:\\mnt\\games\\Skyrim Special Edition\\data\\SKSE\\Plugins\\MantellaSoftware"
    def get_unix_file_name(kernel32, windows_path):
        if windows_path == "Z:\\":
            return "/"
        if windows_path == "C:\\":
            return "/mnt/games/pfx/drive_c"
        if windows_path == "Z:\\home\\user\\Games":
            return "/home/user/Games"
        return "/mnt/mo2/overwrite/SKSE/Plugins/MantellaSoftware" # where Wine says the virtual folder is
    monkeypatch.setattr(wine, "_get_unix_file_name", get_unix_file_name)
    monkeypatch.setattr(wine, "to_windows_path", lambda host_path: "Z:" + host_path.replace("/", "\\"))

    assert wine.to_host_path(virtual_path) == "/mnt/games/Skyrim Special Edition/data/SKSE/Plugins/MantellaSoftware"
    # a path Wine resolves truthfully is converted as before
    assert wine.to_host_path("Z:\\home\\user\\Games") == "/home/user/Games"
    # a drive that is not the host's file system keeps its Windows form
    assert wine.to_host_path("C:\\users\\steamuser\\Documents") == "C:\\users\\steamuser\\Documents"


def test_paths_in_log_messages_are_written_the_host_way():
    """Under Wine, every Windows path in a log message is shown as a path of the host"""
    roots = {'Z': '/', 'C': '/mnt/games/compatdata/489830/pfx/drive_c'}
    convert = lambda text: wine.convert_windows_paths_in_text(text, lambda letter: roots.get(letter.upper()))

    assert convert("Loaded 8 actions from: \n    Z:\\mnt\\games\\Skyrim Special Edition\\data\\actions") == \
        "Loaded 8 actions from: \n    /mnt/games/Skyrim Special Edition/data/actions"
    assert convert("C:/users/steamuser/Documents/My Games/Mantella/data/Skyrim/conversations/Nick1/Fisherman - 097977 does not exist.") == \
        "/mnt/games/compatdata/489830/pfx/drive_c/users/steamuser/Documents/My Games/Mantella/data/Skyrim/conversations/Nick1/Fisherman - 097977 does not exist."
    assert convert('Could not run Piper. Ensure that the path "Z:\\opt\\piper" is correct.') == 'Could not run Piper. Ensure that the path "/opt/piper" is correct.'
    assert convert("two paths: Z:\\a\\b\nand C:\\users") == "two paths: /a/b\nand /mnt/games/compatdata/489830/pfx/drive_c/users"
    # left alone: URLs, times, drives Wine does not know, and text without paths
    assert convert("http://localhost:4999/ui") == "http://localhost:4999/ui"
    assert convert("[10:22:39] Ratio 4:3") == "[10:22:39] Ratio 4:3"
    assert convert("Q:\\unknown\\drive") == "Q:\\unknown\\drive"
    assert convert("") == ""


def test_log_filter_rewrites_messages(monkeypatch):
    import logging
    monkeypatch.setattr(wine, "_get_drive_root", lambda letter: '/' if letter.upper() == 'Z' else None)
    record = logging.LogRecord("Mantella", logging.INFO, __file__, 1, "Running in %s", ("Z:\\mnt\\games",), None)
    assert wine.HostPathLogFilter().filter(record) is True
    assert record.getMessage() == "Running in /mnt/games"
