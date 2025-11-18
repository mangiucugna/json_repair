import pytest

from src.json_repair.json_repair import repair_json


def test_strict_rejects_multiple_top_level_values():
    with pytest.raises(ValueError, match="Multiple top-level JSON elements"):
        repair_json("{}[]", strict=True)


def test_strict_duplicate_keys_inside_array():
    payload = '[{"key": "first", "key": "second"}]'
    with pytest.raises(ValueError, match="Duplicate key found"):
        repair_json(payload, strict=True, skip_json_loads=True)


def test_strict_rejects_empty_keys():
    payload = '{"" : "value"}'
    with pytest.raises(ValueError, match="Empty key found"):
        repair_json(payload, strict=True, skip_json_loads=True)


def test_strict_requires_colon_between_key_and_value():
    with pytest.raises(ValueError, match="Missing ':' after key"):
        repair_json('{"missing" "colon"}', strict=True)


def test_strict_rejects_empty_values():
    payload = '{"key": , "key2": "value2"}'
    with pytest.raises(ValueError, match="Parsed value is empty"):
        repair_json(payload, strict=True, skip_json_loads=True)


def test_strict_rejects_empty_object_with_extra_characters():
    with pytest.raises(ValueError, match="Parsed object is empty"):
        repair_json('{"dangling"}', strict=True)


def test_strict_detects_immediate_doubled_quotes():
    with pytest.raises(ValueError, match="doubled quotes followed by another quote\\.$"):
        repair_json('{"key": """"}', strict=True)


def test_strict_detects_doubled_quotes_followed_by_string():
    with pytest.raises(
        ValueError,
        match="doubled quotes followed by another quote while parsing a string",
    ):
        repair_json('{"key": "" "value"}', strict=True)
