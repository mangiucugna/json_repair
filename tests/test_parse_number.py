from src.json_repair.json_repair import repair_json


def test_parse_number():
    assert repair_json("1", return_objects=True) == 1
    assert repair_json("1.2", return_objects=True) == 1.2


def test_parse_number_edge_cases():
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
    assert repair_json("[1, 2notanumber]") == '[1, "2notanumber"]'
