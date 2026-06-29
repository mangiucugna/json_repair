from typing import TYPE_CHECKING, Literal

from ..utils.constants import STRING_DELIMITERS  # noqa: TID252

if TYPE_CHECKING:
    from ..json_parser import JSONParser  # noqa: TID252


ObjectValueCommaClassification = Literal["container", "member", "string", "string_no_future_delimiter"]


def classify_object_value_comma(parser: "JSONParser") -> ObjectValueCommaClassification:
    next_idx = parser.scroll_whitespaces(idx=1)
    next_c = parser.get_char_at(next_idx)
    if next_c in ["}", None]:
        return "member"

    if next_c in STRING_DELIMITERS:
        key_end_idx = parser.skip_to_character(character=next_c, idx=next_idx + 1)
        if not parser.get_char_at(key_end_idx):
            return "string"
        key_end_idx = parser.scroll_whitespaces(idx=key_end_idx + 1)
        return "member" if parser.get_char_at(key_end_idx) == ":" else "string"

    if next_c == "`":
        bare_key_idx = next_idx + 1
        while True:
            key_char = parser.get_char_at(bare_key_idx)
            if not key_char or not (key_char.isalnum() or key_char in ["_", "-"]):
                break
            bare_key_idx += 1
        bare_key_idx = parser.scroll_whitespaces(idx=bare_key_idx)
        return "member" if parser.get_char_at(bare_key_idx) == ":" else "string"

    if next_c and (next_c.isalnum() or next_c == "_"):
        bare_key_idx = next_idx
        while True:
            key_char = parser.get_char_at(bare_key_idx)
            if not key_char or not (key_char.isalnum() or key_char in ["_", "-"]):
                break
            bare_key_idx += 1
        bare_key_idx = parser.scroll_whitespaces(idx=bare_key_idx)
        if parser.get_char_at(bare_key_idx) == ":":
            return "member"

    if next_c in ["{", "["]:
        return "container"

    next_special_idx = parser.skip_to_character(character=[*STRING_DELIMITERS, "{", "["], idx=next_idx)
    next_special = parser.get_char_at(next_special_idx)
    if not next_special:
        return "string_no_future_delimiter"
    if next_special in ["{", "["]:
        return "string"

    key_end_idx = parser.skip_to_character(character=next_special, idx=next_special_idx + 1)
    if not parser.get_char_at(key_end_idx):
        return "string"
    key_end_idx = parser.scroll_whitespaces(idx=key_end_idx + 1)
    return "member" if parser.get_char_at(key_end_idx) == ":" else "string"


def update_inline_container_stack(
    char: str,
    pending_inline_container: bool,
    inline_container_stack: list[str],
) -> tuple[bool, bool]:
    if char in ["{", "["]:
        if pending_inline_container:
            inline_container_stack.append(char)
            return False, False
        if inline_container_stack:
            inline_container_stack.append(char)

    if inline_container_stack and (
        (char == "}" and inline_container_stack[-1] == "{") or (char == "]" and inline_container_stack[-1] == "[")
    ):
        inline_container_stack.pop()
        return pending_inline_container, True

    return pending_inline_container, False
