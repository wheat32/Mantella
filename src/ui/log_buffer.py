import logging
import threading
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
