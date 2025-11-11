from typing import TYPE_CHECKING

from .utils.constants import JSONReturnType
from .utils.json_context import ContextValues

NUMBER_CHARS: set[str] = set("0123456789-.eE/,")


if TYPE_CHECKING:
    from .json_parser import JSONParser


def parse_number(self: "JSONParser") -> JSONReturnType:
    # <number> is a valid real number expressed in one of a number of given formats
    number_str = ""
    char = self.get_char_at()
    is_array = self.context.current == ContextValues.ARRAY
    while char and char in NUMBER_CHARS and (not is_array or char != ","):
        number_str += char
        self.index += 1
        char = self.get_char_at()
    if number_str and number_str[-1] in "-eE/,":
        # The number ends with a non valid character for a number/currency, rolling back one
        number_str = number_str[:-1]
        self.index -= 1
    elif (self.get_char_at() or "").isalpha():
        # this was a string instead, sorry
        self.index -= len(number_str)
        return self.parse_string()
    try:
        if "," in number_str:
            return str(number_str)
        if "." in number_str or "e" in number_str or "E" in number_str:
            return float(number_str)
        else:
            return int(number_str)
    except ValueError:
        return number_str
