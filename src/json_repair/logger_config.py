from typing import Dict, List, Optional


class LoggerConfig:
    # This is a type class to simplify the declaration
    def __init__(self, log_level: Optional[str]):
        self.log: List[Dict[str, str]] = []
        self.window: int = 10
        self.log_level: str = log_level if log_level else "none"
