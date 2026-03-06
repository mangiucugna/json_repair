from collections.abc import Mapping
from typing import Any

_UNSUPPORTED_REGEX_TOKENS = frozenset({".", "^", "$", "*", "+", "?", "{", "}", "[", "]", "|", "(", ")", "\\"})


def match_pattern_properties(
    pattern_properties: Mapping[str, Any],
    key: str,
) -> tuple[list[Any], list[str]]:
    """Match JSON Schema patternProperties using a safe literal+anchor subset.

    Supported forms:
    - "token"      -> key contains token
    - "^token"     -> key starts with token
    - "token$"     -> key ends with token
    - "^token$"    -> key equals token

    Any pattern using additional regex tokens is treated as unsupported and skipped.
    The caller can log unsupported patterns using the returned list.
    """

    if not pattern_properties:
        return [], []

    matched_schemas: list[Any] = []
    unsupported_patterns: list[str] = []

    for pattern, schema in pattern_properties.items():
        anchored_start = pattern.startswith("^")
        anchored_end = pattern.endswith("$")
        literal = pattern[1 if anchored_start else 0 : -1 if anchored_end else None]

        if any(token in literal for token in _UNSUPPORTED_REGEX_TOKENS):
            unsupported_patterns.append(pattern)
            continue

        if anchored_start and anchored_end:
            is_match = key == literal
        elif anchored_start:
            is_match = key.startswith(literal)
        elif anchored_end:
            is_match = key.endswith(literal)
        else:
            is_match = literal in key

        if is_match:
            matched_schemas.append(schema)

    return matched_schemas, unsupported_patterns
