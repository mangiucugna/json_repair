from typing import TYPE_CHECKING

from .utils.constants import JSONReturnType
from .utils.json_context import ContextValues

if TYPE_CHECKING:
    from .json_parser import JSONParser


def skip_comment(self: "JSONParser") -> None:
    """Consume one comment without parsing any following JSON value."""
    char = self.get_char_at()
    if char == "#" or (char == "/" and self.get_char_at(1) == "/"):
        termination_characters = ["\n", "\r"]
        if char == "#":
            if ContextValues.ARRAY in self.context.context:
                termination_characters.append("]")
            if ContextValues.OBJECT_VALUE in self.context.context:
                termination_characters.append("}")
            if ContextValues.OBJECT_KEY in self.context.context:
                termination_characters.append(":")
        comment = ""
        while char and char not in termination_characters:
            comment += char
            self.index += 1
            char = self.get_char_at()
        self.log(f"Found line comment: {comment}, ignoring")
    elif char == "/" and self.get_char_at(1) == "*":
        comment = "/*"
        self.index += 2
        while True:
            char = self.get_char_at()
            if not char:
                self.log("Reached end-of-string while parsing block comment; unclosed block comment.")
                break
            comment += char
            self.index += 1
            if comment.endswith("*/"):
                break
        self.log(f"Found block comment: {comment}, ignoring")
    elif char == "/":
        # Make progress on standalone slashes that reach the repair fallback.
        self.index += 1


def parse_comment(self: "JSONParser", record_top_level_value: bool = False) -> JSONReturnType:
    """Skip comments and resume value parsing only at the top level."""
    while True:
        skip_comment(self)
        if not self.context.empty:
            return ""
        # Keep long runs of top-level comments iterative.
        self.skip_whitespaces()
        if self.get_char_at() not in ["#", "/"]:
            return self.parse_json(record_top_level_value=record_top_level_value)
