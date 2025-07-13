from typing import TYPE_CHECKING

from .constants import STRING_DELIMITERS, JSONReturnType
from .json_context import ContextValues
from .object_comparer import ObjectComparer

if TYPE_CHECKING:
    from .json_parser import JSONParser


def parse_array(self: "JSONParser") -> list[JSONReturnType]:
    # <array> ::= '[' [ <json> *(', ' <json>) ] ']' ; A sequence of JSON values separated by commas
    arr = []
    self.context.set(ContextValues.ARRAY)
    # Stop when you either find the closing parentheses or you have iterated over the entire string
    char = self.get_char_at()
    while char and char not in ["]", "}"]:
        self.skip_whitespaces_at()
        value: JSONReturnType = ""
        if char in STRING_DELIMITERS:
            # Sometimes it can happen that LLMs forget to start an object and then you think it's a string in an array
            # So we are going to check if this string is followed by a : or not
            # And either parse the string or parse the object
            i = 1
            i = self.skip_to_character(char, i)
            i = self.skip_whitespaces_at(idx=i + 1, move_main_index=False)
            value = self.parse_object() if self.get_char_at(i) == ":" else self.parse_string()
        else:
            value = self.parse_json()

        # It is possible that parse_json() returns nothing valid, so we increase by 1
        if ObjectComparer.is_strictly_empty(value):
            self.index += 1
        elif value == "..." and self.get_char_at(-1) == ".":
            self.log(
                "While parsing an array, found a stray '...'; ignoring it",
            )
        else:
            arr.append(value)

        # skip over whitespace after a value but before closing ]
        char = self.get_char_at()
        while char and char != "]" and (char.isspace() or char == ","):
            self.index += 1
            char = self.get_char_at()

    # Especially at the end of an LLM generated json you might miss the last "]"
    if char and char != "]":
        self.log(
            "While parsing an array we missed the closing ], ignoring it",
        )

    self.index += 1

    self.context.reset()
    return arr
