from collections.abc import Iterator
from typing import TYPE_CHECKING

from .utils.constants import STRING_DELIMITERS

if TYPE_CHECKING:
    from .json_parser import JSONParser


def _scan_parenthesized(parser: "JSONParser", *, allow_unmatched_close: bool) -> Iterator[tuple[int, str, bool]]:
    """Yield unquoted characters with their index and top-level status."""
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
            yield i, ch, nested_parentheses == 0 and square_brackets == 0 and braces == 0
            i += 1
            continue

        backslashes = 0

        is_top_level = nested_parentheses == 0 and square_brackets == 0 and braces == 0
        yield i, ch, is_top_level

        if ch == "(":
            nested_parentheses += 1
        elif ch == ")":
            if nested_parentheses > 0 or allow_unmatched_close:
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


def parenthesized_is_explicit_tuple(parser: "JSONParser") -> bool:
    """Return whether the current '(' starts an explicit Python tuple literal."""
    saw_top_level_content = False
    for _, ch, is_top_level in _scan_parenthesized(parser, allow_unmatched_close=False):
        if not is_top_level:
            continue
        if ch == ",":
            return True
        if ch == ")":
            return not saw_top_level_content
        if not ch.isspace():
            saw_top_level_content = True
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

    inner_text = parser.json_str[parser.index + idx : parser.index + idx + 5].lower()
    if (
        first_inner_char not in [")", "{", "[", "(", *STRING_DELIMITERS]
        and not first_inner_char.isdigit()
        and first_inner_char not in ["-", "."]
        and inner_text[:4] not in ["true", "null", "none"]
        and inner_text[:5] != "false"
    ):
        return False

    n = len(parser.json_str)
    for i, ch, is_top_level in _scan_parenthesized(parser, allow_unmatched_close=True):
        if ch == ")" and is_top_level:
            trailer_index = i + 1
            while trailer_index < n:
                trailer = parser.json_str[trailer_index]
                if trailer in "\n\r":
                    return True
                if not trailer.isspace():
                    return False
                trailer_index += 1
            return True

    return True
