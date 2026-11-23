"""Detection of, and workarounds for, running the Windows build of Mantella under Wine / Proton (ie on Linux).

This module must stay free of heavy imports: `apply_wine_workarounds` has to run before
libraries such as onnxruntime, ctranslate2 (faster_whisper) and huggingface_hub are imported.
"""
import os
import platform
from functools import lru_cache


@lru_cache(maxsize=1)
def is_running_under_wine() -> bool:
    """Whether this process is a Windows process hosted by Wine / Proton"""
    if platform.system() != "Windows":
        return False
    try:
        import ctypes
        return hasattr(ctypes.windll.ntdll, "wine_get_version")
    except Exception:
        return False


def apply_wine_workarounds() -> bool:
    """Sets the environment up so that native libraries behave under Wine. Does nothing on real Windows / native Linux.

    Returns:
        bool: whether the workarounds were applied
    """
    if not is_running_under_wine():
        return False

    # Intel OpenMP (bundled with ctranslate2) queries the CPU layout through Windows APIs that Wine does not implement,
    # and deliberately aborts the process when they fail. A flat topology with no thread pinning avoids these calls
    os.environ.setdefault("KMP_TOPOLOGY_METHOD", "flat")
    os.environ.setdefault("KMP_AFFINITY", "disabled")

    # Symlinks are deliberately not used for Hugging Face downloads under Wine (see disable_hugging_face_symlinks), so skip the warning about it
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    return True


def disable_hugging_face_symlinks() -> bool:
    """Makes huggingface_hub copy real files into its cache instead of symlinking them when running under Wine.
    Symlinks created by the downloader end up as zero-byte placeholder files under Wine, which model loaders then crash on

    Returns:
        bool: whether symlinks were disabled
    """
    if not is_running_under_wine():
        return False
    try:
        from huggingface_hub import file_download
        file_download.are_symlinks_supported = lambda cache_dir=None: False
        return True
    except Exception:
        return False


def to_host_path(path: str) -> str:
    """Converts a Windows path to the path it has on the host system when running under Wine (eg 'Z:\\home\\user' -> '/home/user').
    Used to show users paths they can actually open on their system. Returns the path unchanged outside of Wine or if it cannot be converted
    """
    if not path or not is_running_under_wine():
        return path
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        convert = kernel32.wine_get_unix_file_name
        convert.argtypes = [ctypes.c_wchar_p]
        convert.restype = ctypes.c_void_p
        absolute_path = os.path.abspath(path)
        pointer = convert(absolute_path)
        if not pointer:
            return path
        try:
            host_path = ctypes.string_at(pointer).decode('utf-8', errors='replace')
        finally:
            _free_wine_string(kernel32, pointer)
        # Paths inside a mod manager's virtual folders (eg the game's Data folder under Mod Organizer 2) have no single place
        # on the host: the conversion ends up somewhere else, such as the manager's overwrite folder. Converting the
        # result back shows whether that happened, in which case the Windows path is the more truthful one to display
        if not host_path or not _is_same_windows_path(to_windows_path(host_path), absolute_path):
            return path
        return host_path
    except Exception:
        return path


def _is_same_windows_path(first: str, second: str) -> bool:
    def normalize(windows_path: str) -> str:
        return os.path.normcase(os.path.normpath(windows_path)).replace('/', '\\').rstrip('\\').lower()
    return normalize(first) == normalize(second)


def to_windows_path(path: str) -> str:
    """Converts a path of the host system to a Windows path when running under Wine (eg '/home/user' -> 'Z:\\home\\user'),
    so that Linux paths can be used in settings. Returns the path unchanged outside of Wine, or if it is not an absolute host path
    """
    if not path or not path.startswith('/') or path.startswith('//') or not is_running_under_wine():
        return path
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        convert = kernel32.wine_get_dos_file_name
        convert.argtypes = [ctypes.c_char_p]
        convert.restype = ctypes.c_void_p
        pointer = convert(path.encode('utf-8'))
        if not pointer:
            return path
        try:
            return ctypes.wstring_at(pointer) or path
        finally:
            _free_wine_string(kernel32, pointer)
    except Exception:
        return path


def _free_wine_string(kernel32, pointer) -> None:
    """Frees a string returned by Wine's path conversion functions, which are allocated on the process heap"""
    try:
        import ctypes
        kernel32.GetProcessHeap.restype = ctypes.c_void_p
        kernel32.HeapFree.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p]
        kernel32.HeapFree(kernel32.GetProcessHeap(), 0, pointer)
    except Exception:
        pass
