from typing import TYPE_CHECKING

from .utils.constants import STRING_DELIMITERS

if TYPE_CHECKING:
    from .json_parser import JSONParser


def parenthesized_is_explicit_tuple(parser: "JSONParser") -> bool:
    """
    Return True when the current '(' starts an explicit Python tuple literal.

    Empty parentheses count as a tuple. A single grouped value like ``(1)`` does not.
    """
    i = parser.index + 1
    n = len(parser.json_str)
    nested_parentheses = 0
    square_brackets = 0
    braces = 0
    in_quote: str | None = None
    backslashes = 0
    saw_top_level_content = False

    while i < n:
        ch = parser.json_str[i]

        if ch == "\\":
            backslashes += 1
            i += 1
            continue

        if in_quote is not None:
            if ch == in_quote and backslashes % 2 == 0:
                in_quote = None
            backslashes = 0
            i += 1
            continue

        if ch in STRING_DELIMITERS and backslashes % 2 == 0:
            in_quote = ch
            saw_top_level_content = saw_top_level_content or (
                nested_parentheses == 0 and square_brackets == 0 and braces == 0
            )
            backslashes = 0
            i += 1
            continue

        backslashes = 0

        if (
            not ch.isspace()
            and ch not in [",", ")"]
            and nested_parentheses == 0
            and square_brackets == 0
            and braces == 0
        ):
            saw_top_level_content = True

        if ch == "(":
            nested_parentheses += 1
        elif ch == ")":
            if nested_parentheses == 0 and square_brackets == 0 and braces == 0:
                return not saw_top_level_content
            if nested_parentheses > 0:
                nested_parentheses -= 1
        elif ch == "[":
            square_brackets += 1
        elif ch == "]" and square_brackets > 0:
            square_brackets -= 1
        elif ch == "{":
            braces += 1
        elif ch == "}" and braces > 0:
            braces -= 1
        elif ch == "," and nested_parentheses == 0 and square_brackets == 0 and braces == 0:
            return True

        i += 1

    return not saw_top_level_content


def top_level_parenthesized_can_start_value(parser: "JSONParser") -> bool:
    """
    Return True when a top-level '(' looks like a standalone value rather than inline prose.

    This keeps tuple support available for direct inputs and fenced blocks while avoiding
    regressions on surrounding explanatory text like ``foo (clarification): {...}``.
    """
    i = parser.index - 1
    while i >= 0:
        ch = parser.json_str[i]
        if ch in "\n\r":
            break
        if not ch.isspace():
            return False
        i -= 1

    idx = parser.scroll_whitespaces(idx=1)
    first_inner_char = parser.get_char_at(idx)
    if first_inner_char is None:
        return False

    if (
        first_inner_char not in [")", "{", "[", "(", *STRING_DELIMITERS]
        and not first_inner_char.isdigit()
        and first_inner_char not in ["-", "."]
        and parser.json_str[parser.index + idx : parser.index + idx + 4] not in ["true", "null"]
        and parser.json_str[parser.index + idx : parser.index + idx + 5] != "false"
    ):
        return False

    i = parser.index + 1
    n = len(parser.json_str)
    nested_parentheses = 0
    square_brackets = 0
    braces = 0
    in_quote: str | None = None
    backslashes = 0

    while i < n:
        ch = parser.json_str[i]

        if ch == "\\":
            backslashes += 1
            i += 1
            continue

        if in_quote is not None:
            if ch == in_quote and backslashes % 2 == 0:
                in_quote = None
            backslashes = 0
            i += 1
            continue

        if ch in STRING_DELIMITERS and backslashes % 2 == 0:
            in_quote = ch
            backslashes = 0
            i += 1
            continue

        backslashes = 0

        if ch == "(":
            nested_parentheses += 1
        elif ch == ")":
            if nested_parentheses == 0 and square_brackets == 0 and braces == 0:
                i += 1
                while i < n:
                    trailer = parser.json_str[i]
                    if trailer in "\n\r":
                        return True
                    if not trailer.isspace():
                        return False
                    i += 1
                return True
            nested_parentheses -= 1
        elif ch == "[":
            square_brackets += 1
        elif ch == "]" and square_brackets > 0:
            square_brackets -= 1
        elif ch == "{":
            braces += 1
        elif ch == "}" and braces > 0:
            braces -= 1

        i += 1

    return True
