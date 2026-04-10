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


def test_parse_many_top_level_comments_without_recursion_error():
    comment_count = 600
    raw = ("# comment\n" * comment_count) + '{"key": "value"}'

    repaired, logs = repair_json(raw, return_objects=True, skip_json_loads=True, logging=True)

    assert repaired == {"key": "value"}
    assert len(logs) == comment_count
    assert all(log["text"] == "Found line comment: # comment, ignoring" for log in logs)
