from enum import Enum, auto
from types import TracebackType
from typing import Literal


class ContextValues(Enum):
    OBJECT_KEY = auto()
    OBJECT_VALUE = auto()
    ARRAY = auto()


class _JsonContextEntry:
    __slots__ = ("context", "value")

    def __init__(self, context: "JsonContext", value: ContextValues) -> None:
        self.context = context
        self.value = value

    def __enter__(self) -> None:
        self.context.set(self.value)

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc: BaseException | None,
        _traceback: TracebackType | None,
    ) -> Literal[False]:
        self.context.reset()
        return False


class JsonContext:
    def __init__(self) -> None:
        self.context: list[ContextValues] = []
        self.current: ContextValues | None = None
        self.empty: bool = True

    def enter(self, value: ContextValues) -> _JsonContextEntry:
        return _JsonContextEntry(self, value)

    def set(self, value: ContextValues) -> None:
        """
        Set a new context value.

        Args:
            value (ContextValues): The context value to be added.

        Returns:
            None
        """
        self.context.append(value)
        self.current = value
        self.empty = False

    def reset(self) -> None:
        """
        Remove the most recent context value.

        Returns:
            None
        """
        try:
            self.context.pop()
            self.current = self.context[-1]
        except IndexError:
            self.current = None
            self.empty = True

    def clear(self) -> None:
        """
        Remove all context values.

        Returns:
            None
        """
        self.context.clear()
        self.current = None
        self.empty = True
