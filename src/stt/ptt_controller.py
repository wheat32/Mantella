import json
import os
import sys
import logging

if sys.platform.startswith('win'):
    import ctypes


class PTTController:
    """Lightweight push-to-talk key state checker (Windows-focused).

    - Accepts a human-friendly key string (eg 'V', 'SPACE', 'F1').
    - Polls key state using GetAsyncKeyState.
    - On non-Windows platforms, always returns False.
    """

    def __init__(self, key: str | None) -> None:
        self._vk: int | None = None
        self._is_windows: bool = sys.platform.startswith('win')
        self.update_key(key)

    _SPECIAL_KEYS: dict[str, int] = {
        'SPACE': 0x20,
        'TAB': 0x09,
        'ESC': 0x1B,
        'ESCAPE': 0x1B,
        'ENTER': 0x0D,
        'RETURN': 0x0D,
        'SHIFT': 0x10,
        'CTRL': 0x11,
        'CONTROL': 0x11,
        'ALT': 0x12,
        'CAPSLOCK': 0x14,
        'LEFT': 0x25,
        'UP': 0x26,
        'RIGHT': 0x27,
        'DOWN': 0x28,
        'MOUSE1': 0x01,
        'MOUSE2': 0x02,
        'MOUSE3': 0x04,
        'MOUSE4': 0x05,
        'MOUSE5': 0x06,
    }

    SAVED_SETTINGS_FILE_NAME: str = 'push_to_talk.json'
    _SCAN_CODE_PREFIX: str = 'SC' # a key that is only known by the code the game gave for it, eg 'SC51'
    _MAX_SCAN_CODE: int = 127
    _MAPVK_VSC_TO_VK: int = 1

    @staticmethod
    def _normalize_key_to_vk(key: str | None) -> int | None:
        if not key:
            return None

        k = key.strip().upper()
        if not k:
            return None

        # Letters A-Z and digits 0-9 map directly to VK codes
        if len(k) == 1:
            c = k[0]
            if 'A' <= c <= 'Z':
                return ord(c)
            if '0' <= c <= '9':
                return ord(c)

        # Function keys F1-F24
        if k.startswith('F') and k[1:].isdigit():
            try:
                n = int(k[1:])
                if 1 <= n <= 24:
                    return 0x70 + (n - 1)  # VK_F1 = 0x70
            except Exception:
                return None

        if k in PTTController._SPECIAL_KEYS:
            return PTTController._SPECIAL_KEYS[k]

        scan_code = PTTController._get_scan_code(k)
        if scan_code is not None and sys.platform.startswith('win'):
            vk = ctypes.windll.user32.MapVirtualKeyW(scan_code, PTTController._MAPVK_VSC_TO_VK)
            return vk if vk else None
        return None

    @staticmethod
    def _get_scan_code(key: str) -> int | None:
        """The scan code of a key written as 'SC<number>', None for any other key"""
        number = key[len(PTTController._SCAN_CODE_PREFIX):]
        if key.startswith(PTTController._SCAN_CODE_PREFIX) and number.isdigit() and 0 < int(number) <= PTTController._MAX_SCAN_CODE:
            return int(number)
        return None

    # DirectInput scan codes, which is what the game uses for its key bindings
    _GAME_KEY_CODES: dict[str, int] = {
        'ESC': 1, 'ESCAPE': 1,
        '1': 2, '2': 3, '3': 4, '4': 5, '5': 6, '6': 7, '7': 8, '8': 9, '9': 10, '0': 11,
        'TAB': 15,
        'Q': 16, 'W': 17, 'E': 18, 'R': 19, 'T': 20, 'Y': 21, 'U': 22, 'I': 23, 'O': 24, 'P': 25,
        'ENTER': 28, 'RETURN': 28,
        'CTRL': 29, 'CONTROL': 29,
        'A': 30, 'S': 31, 'D': 32, 'F': 33, 'G': 34, 'H': 35, 'J': 36, 'K': 37, 'L': 38,
        'SHIFT': 42,
        'Z': 44, 'X': 45, 'C': 46, 'V': 47, 'B': 48, 'N': 49, 'M': 50,
        'ALT': 56, 'SPACE': 57, 'CAPSLOCK': 58,
        'F1': 59, 'F2': 60, 'F3': 61, 'F4': 62, 'F5': 63, 'F6': 64, 'F7': 65, 'F8': 66, 'F9': 67, 'F10': 68, 'F11': 87, 'F12': 88,
        'UP': 200, 'LEFT': 203, 'RIGHT': 205, 'DOWN': 208,
        'MOUSE1': 256, 'MOUSE2': 257, 'MOUSE3': 258, 'MOUSE4': 259, 'MOUSE5': 260,
    }

    @staticmethod
    def get_game_key_code(key: str | None) -> int | None:
        """The code the game knows a push-to-talk key by (eg 'V' -> 47), or None if the key has no known code"""
        if not key:
            return None
        k = key.strip().upper()
        return PTTController._GAME_KEY_CODES.get(k, PTTController._get_scan_code(k))

    @staticmethod
    def get_key_name(game_key_code: int | None) -> str | None:
        """The name of the key the game knows by the given code (eg 47 -> 'V'), or None if the code is not one of a usable key"""
        if not isinstance(game_key_code, int) or isinstance(game_key_code, bool) or game_key_code <= 0:
            return None
        for name, code in PTTController._GAME_KEY_CODES.items():
            if code == game_key_code:
                return name
        if game_key_code <= PTTController._MAX_SCAN_CODE:
            return f'{PTTController._SCAN_CODE_PREFIX}{game_key_code}'
        return None

    @staticmethod
    def load_saved_settings(save_folder: str, default_enabled: bool, default_key: str) -> tuple[bool, str]:
        """Push-to-talk is switched on and its key is set in the game's mod menu. The game only tells Mantella about them once a
        conversation starts, so what it last reported is remembered between runs

        Args:
            save_folder (str): the folder Mantella keeps its data in
            default_enabled (bool): whether push-to-talk is on if the game has not reported anything yet
            default_key (str): the key to use if the game has not reported one yet

        Returns:
            tuple[bool, str]: whether push-to-talk is enabled, and the name of its key
        """
        enabled, key = default_enabled, default_key
        try:
            with open(os.path.join(save_folder, PTTController.SAVED_SETTINGS_FILE_NAME), 'r', encoding='utf-8') as f:
                saved = json.load(f)
            if isinstance(saved, dict):
                if isinstance(saved.get('enabled'), bool):
                    enabled = saved['enabled']
                if isinstance(saved.get('key'), str) and PTTController.get_game_key_code(saved['key']) is not None:
                    key = saved['key']
        except (OSError, ValueError):
            pass
        return enabled, key

    @staticmethod
    def save_settings(save_folder: str, enabled: bool, key: str) -> None:
        try:
            with open(os.path.join(save_folder, PTTController.SAVED_SETTINGS_FILE_NAME), 'w', encoding='utf-8') as f:
                json.dump({'enabled': enabled, 'key': key}, f)
        except OSError as e:
            logging.warning(f'Could not save the push-to-talk settings: {e}')

    def update_key(self, key: str | None) -> None:
        try:
            self._vk = self._normalize_key_to_vk(key)
            if self._vk is None and key:
                logging.warning(f"PTT hotkey '{key}' not recognized. PTT will be disabled until a valid key is set.")
        except Exception as e:
            logging.warning(f"Failed to set PTT key '{key}': {e}")
            self._vk = None

    def is_pressed(self) -> bool:
        if not self._is_windows:
            return False
        if self._vk is None:
            return False
        try:
            return (ctypes.windll.user32.GetAsyncKeyState(self._vk) & 0x8000) != 0
        except Exception:
            return False
