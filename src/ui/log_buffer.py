import logging
import os
from logging.handlers import RotatingFileHandler
import threading
from datetime import datetime
from collections import deque
from typing import Any


class LogBuffer(logging.Handler):
    """Keeps the most recent log messages in memory so that they can be shown in the web UI"""

    def __init__(self, max_entries: int = 2000) -> None:
        super().__init__()
        self.__entries: deque[dict[str, Any]] = deque(maxlen=max_entries)
        self.__lock_entries = threading.Lock()
        self.__next_id: int = 1
        self.setFormatter(logging.Formatter('%(message)s'))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = self.format(record)
        except Exception:
            message = str(record.msg)
        with self.__lock_entries:
            self.__entries.append({
                'id': self.__next_id,
                'level': self.get_severity(record.levelno),
                'label': record.levelname,
                'time': self.formatter.formatTime(record, '%H:%M:%S') if self.formatter else '',
                'message': message,
            })
            self.__next_id += 1

    @staticmethod
    def get_severity(level_number: int) -> str:
        """Maps a (possibly custom) log level onto the severity used to color the message"""
        if level_number in (41, 42, 43): # custom HTTP / queue debug levels sit above logging.ERROR but are not errors
            return 'debug'
        if level_number >= logging.ERROR:
            return 'error'
        if level_number >= logging.WARNING:
            return 'warning'
        if level_number <= logging.DEBUG:
            return 'debug'
        return 'info'

    def get_entries(self, after_id: int = 0) -> list[dict[str, Any]]:
        """Returns all buffered log entries newer than the given entry id"""
        with self.__lock_entries:
            return [entry for entry in self.__entries if entry['id'] > after_id]


_log_buffer: LogBuffer | None = None

def get_log_buffer() -> LogBuffer:
    """The log buffer shared by the logger and the web UI"""
    global _log_buffer
    if _log_buffer is None:
        _log_buffer = LogBuffer()
    return _log_buffer


class ConsoleLogFile:
    """Saves the console output of the current run to its own file (optional, see the `Save Console Logs` setting)"""
    DEFAULT_MAX_FILES = 20
    DEFAULT_MAX_SIZE_MB = 10

    def __init__(self) -> None:
        self.__handler: logging.Handler | None = None
        self.__file_path: str | None = None
        self.__start_time = datetime.now()
        self.__settings: tuple[int, int] | None = None

    @property
    def file_path(self) -> str | None:
        return self.__file_path if self.__handler else None

    def apply_setting(self, enabled: bool, save_folder: str, logger: logging.Logger, max_size_mb: int = DEFAULT_MAX_SIZE_MB, max_files: int = DEFAULT_MAX_FILES) -> str | None:
        """Starts / stops saving console logs depending on the settings

        Args:
            max_size_mb: The size a log file can grow to. When it is reached, the file starts over, keeping the previous part as <name>.log.1
            max_files: How many runs logs are kept for. Older ones are deleted

        Returns:
            str | None: the file logs are saved to, if enabled
        """
        max_size_mb, max_files = max(1, int(max_size_mb)), max(1, int(max_files))
        if self.__handler and self.__settings != (max_size_mb, max_files):
            self.__stop(logger) # start again with the new limits
        if enabled and not self.__handler:
            logs_folder = os.path.join(save_folder, 'logs')
            try:
                os.makedirs(logs_folder, exist_ok=True)
                # one file per run, also if the setting is switched off and on again
                self.__file_path = os.path.join(logs_folder, f"console_{self.__start_time.strftime('%Y%m%d_%H%M%S')}.log")
                self.__remove_old_files(logs_folder, max_files)
                handler = RotatingFileHandler(self.__file_path, maxBytes=max_size_mb * 1024 * 1024, backupCount=1, encoding='utf-8')
                handler.setLevel(logger.level or logging.INFO)
                handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s'))
                # include what has been logged before the setting was read
                if os.path.getsize(self.__file_path) == 0:
                    with open(self.__file_path, 'a', encoding='utf-8') as f:
                        for entry in get_log_buffer().get_entries():
                            f.write(f"{entry['time']} {entry['label']}: {entry['message']}\n")
                logger.addHandler(handler)
                self.__handler = handler
                self.__settings = (max_size_mb, max_files)
            except OSError as e:
                logger.warning(f'Could not save console logs to {logs_folder}: {e}')
                return None
        elif not enabled and self.__handler:
            self.__stop(logger)
        return self.file_path

    def delete_saved_logs(self, save_folder: str, logger: logging.Logger) -> int:
        """Deletes all saved console logs. If logs are being saved, the log of the current run starts over

        Returns:
            int: the number of files deleted
        """
        was_saving, settings = self.__handler is not None, self.__settings
        if was_saving:
            self.__stop(logger)
        logs_folder = os.path.join(save_folder, 'logs')
        deleted = 0
        for file_name in self.__get_log_files(logs_folder):
            try:
                os.remove(os.path.join(logs_folder, file_name))
                deleted += 1
            except OSError:
                pass
        if was_saving and settings:
            self.apply_setting(True, save_folder, logger, settings[0], settings[1])
        return deleted

    def __stop(self, logger: logging.Logger) -> None:
        if self.__handler:
            logger.removeHandler(self.__handler)
            self.__handler.close()
            self.__handler = None

    @staticmethod
    def __get_log_files(logs_folder: str) -> list[str]:
        """The saved console logs, oldest first. A run's log can consist of two files (<name>.log and <name>.log.1)"""
        if not os.path.isdir(logs_folder):
            return []
        return sorted(f for f in os.listdir(logs_folder) if f.startswith('console_') and (f.endswith('.log') or f.endswith('.log.1')))

    def __remove_old_files(self, logs_folder: str, max_files: int) -> None:
        """Keeps the logs of the newest runs only (the current run included)"""
        current = os.path.basename(self.__file_path) if self.__file_path else ''
        runs = sorted({f.removesuffix('.1') for f in self.__get_log_files(logs_folder)} | ({current} if current else set()))
        for old_run in runs[:max(0, len(runs) - max_files)]:
            for file_name in (old_run, old_run + '.1'):
                try:
                    os.remove(os.path.join(logs_folder, file_name))
                except OSError:
                    pass


_console_log_file: ConsoleLogFile | None = None

def get_console_log_file() -> ConsoleLogFile:
    global _console_log_file
    if _console_log_file is None:
        _console_log_file = ConsoleLogFile()
    return _console_log_file
