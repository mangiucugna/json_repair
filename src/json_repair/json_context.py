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
        """
        Set a new context value.

        Args:
            value (ContextValues): The context value to be added.

        Returns:
            None
        """
        # If a value is provided update the context variable and save in stack
        if value:
            self.context.append(value)

    def reset(self) -> None:
        """
        Remove the most recent context value.

        Returns:
            None
        """
        self.context.pop()

    def is_current(self, context: ContextValues) -> bool:
        """
        Check if the given context is the current (most recent) context.

        Args:
            context (ContextValues): The context value to check.

        Returns:
            bool: True if the given context is the same as the most recent context in the stack, False otherwise.
        """
        return self.context[-1] == context

    def is_any(self, context: ContextValues) -> bool:
        """
        Check if the given context exists anywhere in the context stack.

        Args:
            context (ContextValues): The context value to check.

        Returns:
            bool: True if the given context exists in the stack, False otherwise.
        """
        return context in self.context

    def is_empty(self) -> bool:
        """
        Check if the context stack is empty.

        Returns:
            bool: True if the context stack is empty, False otherwise.
        """
        return len(self.context) == 0
