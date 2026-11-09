from io import StringIO

import pytest

from src.json_repair.json_repair import load, repair_json


def test_parse_number() -> None:
    assert repair_json("1", return_objects=True) == 1
    assert repair_json("1.2", return_objects=True) == 1.2
    assert repair_json('{"value": 82_461_110}', return_objects=True) == {"value": 82461110}
    assert repair_json('{"value": 1_234.5_6}', return_objects=True) == {"value": 1234.56}


@pytest.mark.parametrize("skip_json_loads", [False, True])
def test_object_number_followed_by_empty_item(skip_json_loads: bool) -> None:
    raw = '{"a": 1,, "b": 2}'
    result, logs = repair_json(raw, logging=True, skip_json_loads=skip_json_loads)
    assert result == {"a": 1, "b": 2}
    assert any("comma" in entry["text"].lower() for entry in logs)
    assert load(StringIO(raw), skip_json_loads=skip_json_loads, chunk_length=2) == {"a": 1, "b": 2}
    with pytest.raises(ValueError, match="Consecutive commas"):
        repair_json(raw, strict=True, skip_json_loads=skip_json_loads)


def test_object_number_followed_by_consecutive_commas_and_digits() -> None:
    assert repair_json('{"a": 1,,2}', return_objects=True) == {"a": 1}
    assert repair_json('{"a": -1.5,,, "b": 2}', return_objects=True) == {"a": -1.5, "b": 2}


@pytest.mark.parametrize("skip_json_loads", [False, True])
def test_stray_number_after_consecutive_commas_preserves_next_key(skip_json_loads: bool) -> None:
    raw = '{"a":1,,2,"b":3}'
    expected = {"a": 1, "b": 3}
    result, logs = repair_json(raw, logging=True, skip_json_loads=skip_json_loads)
    assert result == expected
    assert any("comma" in entry["text"].lower() for entry in logs)
    assert load(StringIO(raw), skip_json_loads=skip_json_loads, chunk_length=2) == expected
    assert repair_json('{"a":1,, 2 , "b":3}', return_objects=True, skip_json_loads=skip_json_loads) == expected
    assert repair_json('{"a":1,,2:3}', return_objects=True, skip_json_loads=skip_json_loads) == {"a": 1, "2": 3}


def test_comma_containing_object_value_remains_a_string() -> None:
    assert repair_json('{"value": 105,12,', return_objects=True) == {"value": "105,12"}


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('{"value": 1e+10', {"value": 1e10}),
        ('{"value": -2.5E+3', {"value": -2500.0}),
        ("[6.02e+23, 2", [6.02e23, 2]),
        ('{"value": 1e+2, "next": true}', {"value": 100.0, "next": True}),
    ],
)
@pytest.mark.parametrize("skip_json_loads", [False, True])
def test_parse_number_positive_exponent(raw: str, expected: object, skip_json_loads: bool) -> None:
    assert repair_json(raw, return_objects=True, skip_json_loads=skip_json_loads) == expected
    assert load(StringIO(raw), skip_json_loads=skip_json_loads, chunk_length=2) == expected


def test_parse_number_plus_outside_exponent() -> None:
    assert repair_json("[1+2]", return_objects=True) == [1, 2]
    assert repair_json("[1.1.1e+]", return_objects=True) == ["1.1.1e"]


@pytest.mark.parametrize("suffix", ["e", "E", "e+", "E-", "e-"])
@pytest.mark.parametrize("skip_json_loads", [False, True])
def test_dangling_exponent_is_consumed(suffix: str, skip_json_loads: bool) -> None:
    for raw, expected in [
        (f"[1{suffix}, 2]", [1, 2]),
        (f'{{"n": 1{suffix}, "next": 2}}', {"n": 1, "next": 2}),
    ]:
        result, logs = repair_json(raw, logging=True, skip_json_loads=skip_json_loads)
        assert result == expected
        assert any("exponent" in entry["text"].lower() for entry in logs)
        assert load(StringIO(raw), skip_json_loads=skip_json_loads, chunk_length=2) == expected
        with pytest.raises(ValueError, match="exponent"):
            repair_json(raw, strict=True, skip_json_loads=skip_json_loads)


def test_parse_number_edge_cases() -> None:
    assert (
        repair_json(' - { "test_key": ["test_value", "test_value2"] }') == '{"test_key": ["test_value", "test_value2"]}'
    )
    assert repair_json('{"key": 1/3}') == '{"key": "1/3"}'
    assert repair_json('{"key": .25}') == '{"key": 0.25}'
    assert repair_json('{"here": "now", "key": 1/3, "foo": "bar"}') == '{"here": "now", "key": "1/3", "foo": "bar"}'
    assert repair_json('{"key": 12345/67890}') == '{"key": "12345/67890"}'
    assert repair_json("[105,12") == "[105, 12]"
    assert repair_json('{"key", 105,12,') == '{"key": "105,12"}'
    assert repair_json('{"key": 1/3, "foo": "bar"}') == '{"key": "1/3", "foo": "bar"}'
    assert repair_json('{"key": 10-20}') == '{"key": "10-20"}'
    assert repair_json('{"key": 1.1.1}') == '{"key": "1.1.1"}'
    assert repair_json("[- ") == "[]"
    assert repair_json('{"key": 1. }') == '{"key": 1.0}'
    assert repair_json('{"key": 1e10 }') == '{"key": 10000000000.0}'
    assert repair_json('{"key": 1e }') == '{"key": 1}'
    assert repair_json('{"key": 1notanumber }') == '{"key": "1notanumber"}'
    assert (
        repair_json('{"rowId": 57eeeeb1-450b-482c-81b9-4be77e95dee2}')
        == '{"rowId": "57eeeeb1-450b-482c-81b9-4be77e95dee2"}'
    )
    assert repair_json("[1, 2notanumber]") == '[1, "2notanumber"]'


def test_numeric_prefix_identifiers_preserve_underscored_digits() -> None:
    assert repair_json('{"sku": 123_456ABC}', return_objects=True) == {"sku": "123_456ABC"}
    assert repair_json("[1_2_3ABC]", return_objects=True) == ["1_2_3ABC"]
    assert repair_json('{"value": 123_456}', return_objects=True) == {"value": 123456}
