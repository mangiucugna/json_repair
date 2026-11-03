import pytest

from src.json_repair.json_repair import repair_json


@pytest.mark.parametrize("skip_json_loads", [False, True])
@pytest.mark.parametrize("raw", ['"a": 1}', '"a": {"b": 2}}'])
def test_strict_rejects_missing_opening_object_brace(raw: str, skip_json_loads: bool) -> None:
    with pytest.raises(ValueError, match="Missing opening object brace"):
        repair_json(raw, strict=True, skip_json_loads=skip_json_loads)


@pytest.mark.parametrize(
    "payload",
    [
        '{"key":"value"}["value"]',
        '{"key":"value"}, {"key":"value_after"}',
        '{"key":"value"}{"key":"value_after"}',
        "[1][2]",
        '{"key":"value"}[]',
        '{"key":"value"}{}',
        "[]{}",
        "{}[]",
        "[1]{}",
    ],
)
def test_strict_rejects_multiple_top_level_values(payload: str) -> None:
    with pytest.raises(ValueError, match="Multiple top-level JSON elements"):
        repair_json(payload, strict=True)


def test_strict_duplicate_keys_inside_array() -> None:
    payload = '[{"key": "first", "key": "second"}]'
    with pytest.raises(ValueError, match="Duplicate key found"):
        repair_json(payload, strict=True, skip_json_loads=True)


def test_strict_rejects_empty_keys() -> None:
    payload = '{"" : "value"}'
    with pytest.raises(ValueError, match="Empty key found"):
        repair_json(payload, strict=True, skip_json_loads=True)


def test_strict_requires_colon_between_key_and_value() -> None:
    with pytest.raises(ValueError, match="Missing ':' after key"):
        repair_json('{"missing" "colon"}', strict=True)


def test_strict_rejects_empty_values() -> None:
    payload = '{"key": , "key2": "value2"}'
    with pytest.raises(ValueError, match="Parsed value is empty"):
        repair_json(payload, strict=True, skip_json_loads=True)


def test_strict_rejects_empty_object_with_extra_characters() -> None:
    with pytest.raises(ValueError, match="Parsed object is empty"):
        repair_json('{"dangling"}', strict=True)


def test_strict_rejects_empty_escaped_object_with_extra_characters() -> None:
    with pytest.raises(ValueError, match="Parsed object is empty"):
        repair_json('{\\"key\\": \\"value\\"}', strict=True, skip_json_loads=True)


def test_strict_detects_immediate_doubled_quotes() -> None:
    with pytest.raises(ValueError, match=r"doubled quotes followed by another quote\.$"):
        repair_json('{"key": """"}', strict=True)


def test_strict_detects_doubled_quotes_followed_by_string() -> None:
    with pytest.raises(
        ValueError,
        match="doubled quotes followed by another quote while parsing a string",
    ):
        repair_json('{"key": "" "value"}', strict=True)
