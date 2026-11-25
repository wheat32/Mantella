"""Collects the versions of what Mantella runs on and with, for the block of information printed when Mantella starts.
Everything here is best effort: whatever cannot be found out is reported as "unknown" instead of stopping Mantella."""
import glob
import locale
import os
import platform
import re
import sys
from src.config.definitions.game_definitions import GameEnum
from src.wine import is_running_under_wine

UNKNOWN = 'unknown'

GAME_EXECUTABLES: dict[GameEnum, str] = {
    GameEnum.SKYRIM: 'SkyrimSE.exe',
    GameEnum.SKYRIM_VR: 'SkyrimVR.exe',
    GameEnum.FALLOUT4: 'Fallout4.exe',
    GameEnum.FALLOUT4_VR: 'Fallout4VR.exe',
}

# The script extender's library in the game folder, which carries the game version it is for in its name (skse64_1_6_1170.dll)
SCRIPT_EXTENDER_LIBRARIES: dict[GameEnum, tuple[str, str]] = {
    GameEnum.SKYRIM: ('SKSE', 'skse64_*.dll'),
    GameEnum.SKYRIM_VR: ('SKSE VR', 'sksevr_*.dll'),
    GameEnum.FALLOUT4: ('F4SE', 'f4se_*.dll'),
    GameEnum.FALLOUT4_VR: ('F4SE VR', 'f4sevr_*.dll'),
}

MOD_ORGANIZER_LIBRARY = 'usvfs_x64.dll' # Mod Organizer 2's virtual file system, loaded into every program it starts


FIXED_FILE_INFO_SIGNATURE = bytes.fromhex('BD04EFFE') # starts the version block of a Windows program or library (0xFEEF04BD)
FIXED_FILE_INFO_VERSION_OFFSET = 8 # the file version follows the signature and the structure version, as two 32 bit numbers
MAX_VERSION_FILE_SIZE = 512 * 1024 * 1024


def get_file_version(path: str) -> str | None:
    """The version a Windows program or library carries (eg '1.6.1170.0'), read from the file itself so that it also works
    where Windows is not there to ask. None if the file has no version or cannot be read"""
    try:
        if os.path.getsize(path) > MAX_VERSION_FILE_SIZE:
            return None
        with open(path, 'rb') as f:
            content = f.read()
        position = content.find(FIXED_FILE_INFO_SIGNATURE)
        if position < 0:
            return None
        version = content[position + FIXED_FILE_INFO_VERSION_OFFSET:position + FIXED_FILE_INFO_VERSION_OFFSET + 8]
        if len(version) < 8:
            return None
        most_significant = int.from_bytes(version[0:4], 'little')
        least_significant = int.from_bytes(version[4:8], 'little')
        return f'{most_significant >> 16}.{most_significant & 0xFFFF}.{least_significant >> 16}.{least_significant & 0xFFFF}'
    except OSError:
        return None


def format_script_extender_version(file_version: str | None) -> str | None:
    """Script extenders number their libraries as 0.<major>.<minor>.<patch>: '0.2.2.6' is SKSE 2.2.6"""
    if not file_version:
        return None
    parts = file_version.split('.')
    if len(parts) == 4 and parts[0] == '0':
        return '.'.join(parts[1:])
    return file_version


def parse_os_release(text: str) -> str | None:
    """The name of a Linux distribution from the contents of its /etc/os-release file"""
    match = re.search(r'^PRETTY_NAME=(.*)$', text, re.MULTILINE)
    if not match:
        return None
    name = match.group(1).strip().strip('"\'')
    return name or None


def _get_wine_details() -> tuple[str | None, str | None, str | None]:
    """The version of Wine, and the name and release of the system it runs on (eg '10.0', 'Linux', '6.12.1-arch1-1')"""
    try:
        import ctypes
        ntdll = ctypes.windll.ntdll
        ntdll.wine_get_version.restype = ctypes.c_char_p
        wine_version = ntdll.wine_get_version().decode('utf-8', errors='replace')
        system_name, release = ctypes.c_char_p(), ctypes.c_char_p()
        ntdll.wine_get_host_version(ctypes.byref(system_name), ctypes.byref(release))
        return (wine_version,
                system_name.value.decode('utf-8', errors='replace') if system_name.value else None,
                release.value.decode('utf-8', errors='replace') if release.value else None)
    except Exception:
        return None, None, None


def _get_host_distribution() -> str | None:
    """The Linux distribution Wine runs on, read through the drive Wine maps to the root of the host's file system"""
    for path in ('Z:\\etc\\os-release', 'Z:\\usr\\lib\\os-release'):
        try:
            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                name = parse_os_release(f.read())
            if name:
                return name
        except OSError:
            continue
    return None


def _get_proton_version() -> str | None:
    """The version of Proton, from the 'version' file in its folder (eg '1731000000 GE-Proton10-4' -> 'GE-Proton10-4')"""
    for folder in os.environ.get('STEAM_COMPAT_TOOL_PATHS', '').split(':'):
        if not folder:
            continue
        try:
            with open('Z:' + folder.replace('/', '\\') + '\\version', 'r', encoding='utf-8', errors='replace') as f:
                content = f.read().split()
            if content:
                return content[-1]
        except OSError:
            continue
    return None


def get_operating_system() -> list[tuple[str, str]]:
    """The lines describing the operating system: the host system when running under Wine / Proton, with Wine itself on a line of its own"""
    if is_running_under_wine():
        wine_version, host_name, host_release = _get_wine_details()
        distribution = _get_host_distribution()
        lines = [('OS', distribution or host_name or UNKNOWN)]
        if host_release:
            lines.append(('Kernel', host_release))
        proton_version = _get_proton_version()
        is_proton = proton_version is not None or 'STEAM_COMPAT_DATA_PATH' in os.environ
        wine_description = f'Wine {wine_version or UNKNOWN}'
        if proton_version:
            wine_description += f' (Proton {proton_version})'
        elif is_proton:
            wine_description += ' (Proton)'
        lines.append(('Compatibility layer', wine_description))
        return lines
    if platform.system() == 'Windows':
        return [('OS', f'Windows {platform.release()}'.strip()), ('OS build', platform.version() or UNKNOWN)]
    distribution = None
    try:
        with open('/etc/os-release', 'r', encoding='utf-8', errors='replace') as f:
            distribution = parse_os_release(f.read())
    except OSError:
        pass
    return [('OS', distribution or platform.system() or UNKNOWN), ('Kernel', platform.release() or UNKNOWN)]


def is_started_by_mod_organizer() -> bool:
    try:
        import ctypes
        get_module_handle = ctypes.windll.kernel32.GetModuleHandleW
        get_module_handle.restype = ctypes.c_void_p
        get_module_handle.argtypes = [ctypes.c_wchar_p]
        return bool(get_module_handle(MOD_ORGANIZER_LIBRARY))
    except Exception:
        return False


def get_game_details(game: GameEnum, game_path: str | None) -> list[tuple[str, str]]:
    """The versions of the game and of its script extender, read from the files in the game folder"""
    lines: list[tuple[str, str]] = [('Game', game.display_name)]
    executable = GAME_EXECUTABLES.get(game)
    extender_name, extender_pattern = SCRIPT_EXTENDER_LIBRARIES.get(game, ('Script extender', ''))
    if not game_path or not os.path.isdir(game_path):
        lines.append(('Game version', f'{UNKNOWN} (game folder not known)'))
        lines.append((f'{extender_name} version', UNKNOWN))
        return lines

    game_version = get_file_version(os.path.join(game_path, executable)) if executable else None
    lines.append(('Game version', game_version or UNKNOWN))

    extender_libraries = sorted(glob.glob(os.path.join(game_path, extender_pattern))) if extender_pattern else []
    # the loader and Steam's own library match the pattern too, but are not the extender itself
    extender_libraries = [path for path in extender_libraries if not os.path.basename(path).lower().endswith(('_loader.dll', 'steam_loader.dll'))]
    if not extender_libraries:
        lines.append((f'{extender_name} version', 'not found in the game folder'))
    for library in extender_libraries:
        version = format_script_extender_version(get_file_version(library)) or UNKNOWN
        lines.append((f'{extender_name} version', f'{version} ({os.path.basename(library)})'))
    return lines


def get_system_info(mantella_version: str, game: GameEnum, game_path: str | None, is_started_by_game: bool) -> list[tuple[str, str]]:
    """Everything that is printed when Mantella starts, as (label, value) pairs"""
    lines: list[tuple[str, str]] = [('Mantella version', mantella_version or UNKNOWN)]
    lines.append(('Python version', platform.python_version()))
    lines.append(('Build', 'Mantella.exe' if getattr(sys, 'frozen', False) else 'run from source'))
    lines.extend(get_operating_system())
    lines.append(('CPU arch', platform.machine() or UNKNOWN))
    try:
        lines.append(('Locale', locale.getlocale()[0] or UNKNOWN))
    except Exception:
        lines.append(('Locale', UNKNOWN))
    lines.extend(get_game_details(game, game_path))
    lines.append(('Started by', 'the game' if is_started_by_game else 'the user'))
    lines.append(('Mod Organizer 2', 'yes' if is_started_by_mod_organizer() else 'not detected'))
    return lines


def format_system_info(lines: list[tuple[str, str]]) -> list[str]:
    """The lines to print: a header, one aligned line per value, and a closing line"""
    header = '=== Mantella starting ==='
    width = max((len(label) for label, _ in lines), default=0)
    return [header] + [f'{label.ljust(width)} : {value}' for label, value in lines] + ['=' * len(header)]
