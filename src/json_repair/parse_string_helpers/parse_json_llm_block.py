from typing import TYPE_CHECKING

from ..utils.constants import JSONReturnType  # noqa: TID252

if TYPE_CHECKING:
    from ..json_parser import JSONParser  # noqa: TID252


def parse_json_llm_block(parser: "JSONParser") -> JSONReturnType:
    """
    Extracts and normalizes JSON enclosed in ```json ... ``` blocks.

    Returns:
        The parsed block value, or False when no JSON block is found.
    """
    # Try to find a ```json ... ``` block
    if parser.json_str[parser.index : parser.index + 7] == "```json":
        i = parser.skip_to_character("`", idx=7)
        if parser.json_str[parser.index + i : parser.index + i + 3] == "```":
            parser.index += 7  # Move past ```json
            return parser.parse_json()
    return False
