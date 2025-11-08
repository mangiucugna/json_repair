from typing import TYPE_CHECKING

from ..constants import JSONReturnType  # noqa: TID252

if TYPE_CHECKING:
    from ..json_parser import JSONParser  # noqa: TID252


def parse_json_llm_block(self: "JSONParser") -> JSONReturnType:
    """
    Extracts and normalizes JSON enclosed in ```json ... ``` blocks.
    """
    # Try to find a ```json ... ``` block
    if self.json_str[self.index : self.index + 7] == "```json":
        i = self.skip_to_character("`", idx=7)
        if self.json_str[self.index + i : self.index + i + 3] == "```":
            self.index += 7  # Move past ```json
            return self.parse_json()
    return False
