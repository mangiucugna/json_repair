from src.json_repair.json_repair import repair_json


def test_parse_comment():
    assert repair_json("/") == ""
    assert repair_json('/* comment */ {"key": "value"}')
    assert (
        repair_json('{ "key": { "key2": "value2" // comment }, "key3": "value3" }')
        == '{"key": {"key2": "value2"}, "key3": "value3"}'
    )
    assert (
        repair_json('{ "key": { "key2": "value2" # comment }, "key3": "value3" }')
        == '{"key": {"key2": "value2"}, "key3": "value3"}'
    )
    assert (
        repair_json('{ "key": { "key2": "value2" /* comment */ }, "key3": "value3" }')
        == '{"key": {"key2": "value2"}, "key3": "value3"}'
    )
    assert repair_json('[ "value", /* comment */ "value2" ]') == '["value", "value2"]'
    assert repair_json('{ "key": "value" /* comment') == '{"key": "value"}'
