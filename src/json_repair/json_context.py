from enum import Enum, auto
from typing import List


class ContextValues(Enum):
    OBJECT_KEY = auto()
    OBJECT_VALUE = auto()
    ARRAY = auto()


class JsonContext:
    def __init__(self) -> None:
        self.context: List[ContextValues] = []

    def set(self, value: ContextValues) -> None:
        # If a value is provided update the context variable and save in stack
        if value:
            self.context.append(value)

    def reset(self) -> None:
        self.context.pop()

    def is_current(self, context: ContextValues) -> bool:
        return self.context[-1] == context

    def is_any(self, context: ContextValues) -> bool:
        return context in self.context

    def is_empty(self) -> bool:
        return len(self.context) == 0
