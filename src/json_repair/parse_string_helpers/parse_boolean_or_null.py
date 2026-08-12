from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..json_parser import JSONParser  # noqa: TID252


LITERAL_VALUES: dict[str, bool | None] = {
    "true": True,
    "false": False,
    "null": None,
    "none": None,
}


def parse_boolean_or_null(parser: "JSONParser") -> tuple[bool, bool | None]:
    """Return whether an unquoted complete literal was found and its value."""
    char = (parser.get_char_at() or "").lower()
    starting_index = parser.index
    for literal, value in LITERAL_VALUES.items():
        if char != literal[0]:
            continue
        parser.index = starting_index
        for expected_char in literal:
            if (parser.get_char_at() or "").lower() != expected_char:
                break
            parser.index += 1
        else:
            next_char = parser.get_char_at()
            if next_char is None or next_char.isspace() or next_char in {",", ")", "]", "}"}:
                if literal == "none":
                    parser.log("Converted unquoted Python None literal to JSON null")
                return True, value

    parser.index = starting_index
    return False, None
