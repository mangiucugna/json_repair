from json_repair.json_repair import repair_json


def test_parse_boolean_or_null():
    assert repair_json("True", return_objects=True) == ""
    assert repair_json("False", return_objects=True) == ""
    assert repair_json("Null", return_objects=True) == ""
    assert repair_json("true", return_objects=True)
    assert not repair_json("false", return_objects=True)
    assert repair_json("null", return_objects=True) is None
    assert repair_json('  {"key": true, "key2": false, "key3": null}') == '{"key": true, "key2": false, "key3": null}'
    assert repair_json('{"key": TRUE, "key2": FALSE, "key3": Null}   ') == '{"key": true, "key2": false, "key3": null}'
