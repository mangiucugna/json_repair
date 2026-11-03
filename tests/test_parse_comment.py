import pytest

from src.json_repair.json_parser import JSONParser
from src.json_repair.json_repair import repair_json


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('{"a": /* comment */ 1}', {"a": 1}),
        ('{"a": // note\n "x", "b": 2}', {"a": "x", "b": 2}),
        ('{"a": /* c */ {"b": 1}}', {"a": {"b": 1}}),
        ('{"a": # c\n true}', {"a": True}),
        ('{"a": /* first */ # second\n [1, 2]}', {"a": [1, 2]}),
        ('{"a": /* comment */ "", "b": false}', {"a": "", "b": False}),
    ],
)
def test_comments_between_colon_and_object_value(raw: str, expected: object) -> None:
    result, logs = repair_json(raw, return_objects=True, logging=True)
    assert result == expected
    assert any("comment" in entry["text"] for entry in logs)


def test_comment_before_schema_guided_object_value() -> None:
    schema = {"type": "object", "properties": {"a": {"type": "integer"}}, "required": ["a"]}
    assert repair_json('{"a": /* comment */ 1}', schema=schema, return_objects=True) == {"a": 1}


def test_comment_before_missing_object_value_does_not_consume_next_key() -> None:
    assert repair_json('{"a": /* comment */, "b": 2}', return_objects=True) == {"a": "", "b": 2}


def test_comment_between_array_items_preserves_items() -> None:
    assert repair_json('{"a": [1, /* comment */ 2]}', return_objects=True) == {"a": [1, 2]}


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("[/* comment */]", []), ("[1, /* comment */]", [1]), ("[1, /* one */ /* two */]", [1])],
)
def test_comment_before_array_end_is_not_an_item(raw: str, expected: object) -> None:
    assert repair_json(raw, return_objects=True) == expected


def test_comment_before_schema_guided_array_item() -> None:
    schema = {"type": "array", "items": {"type": "integer"}}
    assert repair_json("[/* comment */ 1, /* comment */ 2]", schema=schema, return_objects=True) == [1, 2]


def test_comment_before_schema_guided_array_end() -> None:
    schema = {"type": "array", "items": {"type": "integer"}}
    assert repair_json("[1, /* comment */]", schema=schema, return_objects=True) == [1]


def test_comment_before_empty_array_string_preserves_item() -> None:
    assert repair_json('[/* comment */ ""]', return_objects=True) == [""]


def test_comment_at_nested_array_end_preserves_outer_item() -> None:
    assert repair_json("[/* before */ [1, /* end */], 2]", return_objects=True) == [[1], 2]


def test_comment_before_array_object_recovery() -> None:
    assert repair_json('[/* comment */ "key": "value"]', return_objects=True) == [{"key": "value"}]


def test_comment_before_member_closes_unclosed_array() -> None:
    assert repair_json('{"a": [1, /* comment */ "b": 2}', return_objects=True) == {"a": [1], "b": 2}


def test_comment_does_not_consume_tuple_schema_position() -> None:
    schema = {"type": "array", "prefixItems": [{"type": "integer"}, {"type": "string"}]}
    assert repair_json('[/* comment */, 1, "x"]', schema=schema, return_objects=True) == [1, "x"]


@pytest.mark.parametrize("comment", ["/* comment */", "// comment\n", "# comment\n"])
@pytest.mark.parametrize("strict", [False, True])
def test_comments_between_array_values_preserve_falsy_items_and_logging(comment: str, strict: bool) -> None:
    raw = f'[{comment} 0, {comment} false, {comment} null, {comment} "", {comment}]'

    repaired, logs = repair_json(raw, return_objects=True, logging=True, strict=strict)

    assert repaired == [0, False, None, ""]
    assert len(logs) == 5
    assert all("comment" in entry["text"] and "ignoring" in entry["text"] for entry in logs)


def test_comment_before_missing_object_value_is_rejected_in_strict_mode() -> None:
    with pytest.raises(ValueError, match="Parsed value is empty"):
        repair_json('{"a": /* comment */, "b": 2}', strict=True)


@pytest.mark.parametrize("comment", ["/* comment */", "// comment\n", "# comment\n"])
def test_skipping_comments_with_empty_context_leaves_the_next_value_unparsed(comment: str) -> None:
    parser = JSONParser(f' {comment} {{"a": 1}}', None, True)

    parser.skip_whitespace_and_comments()

    assert parser.json_str[parser.index :] == '{"a": 1}'
    assert len(parser.logger) == 1
    assert "ignoring" in parser.logger[0]["text"]


@pytest.mark.parametrize("comment", ["/* comment */", "// comment\n", "# comment\n"])
@pytest.mark.parametrize("strict", [False, True])
def test_comments_at_object_member_boundaries(comment: str, strict: bool) -> None:
    raw = f'{{{comment} "a" {comment}: 1 {comment}, {comment} "b": 2 {comment}}}'

    repaired, logs = repair_json(raw, return_objects=True, logging=True, strict=strict)

    assert repaired == {"a": 1, "b": 2}
    assert len(logs) == 5
    assert all("comment" in entry["text"] and "ignoring" in entry["text"] for entry in logs)


@pytest.mark.parametrize("comment", ["/* comment */", "// comment\n", "# comment\n"])
def test_comment_only_object_in_strict_mode(comment: str) -> None:
    assert repair_json(f"{{{comment}}}", strict=True, return_objects=True) == {}


@pytest.mark.parametrize("raw", ["{/* unclosed", "{/* unclosed }"])
def test_unclosed_comment_only_object_is_rejected_in_strict_mode(raw: str) -> None:
    with pytest.raises(ValueError, match="Parsed object is empty"):
        repair_json(raw, strict=True)


def test_skipping_comments_leaves_a_standalone_slash_unconsumed() -> None:
    parser = JSONParser("/* comment */ /value", None, True)

    parser.skip_whitespace_and_comments()

    assert parser.json_str[parser.index :] == "/value"
    assert len(parser.logger) == 1


def test_comment_before_colon_with_nested_schema_preserves_string_contents() -> None:
    schema = {"type": "object", "properties": {"a": {"type": "string"}}, "required": ["a"]}
    raw = '[{"a" /* comment */: "keep /* literal */"}]'
    assert repair_json(raw, schema={"type": "array", "items": schema}, return_objects=True) == [
        {"a": "keep /* literal */"}
    ]


@pytest.mark.parametrize("comment", ["/* comment */", "// comment\n", "# comment\n"])
def test_comments_around_recovered_array_continuation_preserve_members(comment: str) -> None:
    raw = f'{{"a": [1], [2] {comment}, {comment} "b": 3}}'
    assert repair_json(raw, return_objects=True) == {"a": [1, 2], "b": 3}


def test_standalone_slash_after_recovered_array_continuation_preserves_members() -> None:
    assert repair_json('{"a": [1], [2] / "b": 3}', return_objects=True) == {"a": [1, 2], "b": 3}


@pytest.mark.parametrize("raw", ["{    ", "{ // comment\n"])
def test_incomplete_empty_objects_with_only_whitespace_or_comments(raw: str) -> None:
    assert repair_json(raw, return_objects=True) == {}


def test_parse_comment() -> None:
    assert repair_json("/") == ""
    assert repair_json('/* comment */ {"key": "value"}') == '{"key": "value"}'
    assert repair_json('{ "key": { "key2": "value2" // comment }, "key3": "value3" }') == '{"key": {"key2": "value2"}}'
    assert (
        repair_json('{ "key": { "key2": "value2" // comment\n}, "key3": "value3" }')
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


def test_line_comment_brackets_do_not_trigger_empty_object_array_fallback() -> None:
    repaired, logs = repair_json("{\n// comment ]\n}", return_objects=True, skip_json_loads=True, logging=True)

    assert repaired == {}
    assert all("try to parse this as an array instead" not in entry["text"] for entry in logs)


def test_block_comment_brackets_do_not_trigger_empty_object_array_fallback() -> None:
    repaired, logs = repair_json("{/* comment ] */}", return_objects=True, skip_json_loads=True, logging=True)

    assert repaired == {}
    assert all("try to parse this as an array instead" not in entry["text"] for entry in logs)


def test_line_comment_brackets_do_not_close_array_items() -> None:
    raw = """
    {
        "Changes": [
            //object a
            {
                "Action": "1"
            },
            //object b ]
            {
                "Action": "2"
            },
            //object c ]
            {
                "Action": "3"
            }
        ]
    }
    """

    assert repair_json(raw, return_objects=True, skip_json_loads=True) == {
        "Changes": [{"Action": "1"}, {"Action": "2"}, {"Action": "3"}]
    }


def test_parse_many_top_level_comments_without_recursion_error() -> None:
    comment_count = 600
    raw = ("# comment\n" * comment_count) + '{"key": "value"}'

    repaired, logs = repair_json(raw, return_objects=True, skip_json_loads=True, logging=True)

    assert repaired == {"key": "value"}
    assert len(logs) == comment_count
    assert all(log["text"] == "Found line comment: # comment, ignoring" for log in logs)
