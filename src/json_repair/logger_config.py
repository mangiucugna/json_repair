from enum import Enum, auto
from typing import Dict, List


class LogLevel(Enum):
    INFO = auto()
    NONE = auto()


class LoggerConfig:
    # This is a type class to simplify the declaration
    def __init__(self, log_level: LogLevel):
        self.log: List[Dict[str, str]] = []
        self.window: int = 10
        self.log_level: LogLevel = log_level if log_level else LogLevel.NONE
