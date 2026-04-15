from io import StringIO

import pytest

from src.json_repair.json_parser import JSONParser
from src.json_repair.json_repair import repair_json
from src.json_repair.parse_string import (
    StringParseState,
    _brace_before_code_fence_belongs_to_string,
    _quoted_object_member_follows,
    _scan_string_body,
    _skip_inline_container,
    _starts_nested_inline_container,
    _try_parse_simple_quoted_string,
)
from src.json_repair.parse_string_helpers.object_value_context import update_inline_container_stack
from src.json_repair.utils.json_context import ContextValues
from src.json_repair.utils.string_file_wrapper import StringFileWrapper


def _assert_object_repairs(raw: str, expected: dict) -> None:
    assert repair_json(raw, return_objects=True) == expected
    assert repair_json(raw, skip_json_loads=True, return_objects=True) == expected


def test_parse_string():
    assert repair_json('"') == ""
    assert repair_json("\n") == ""
    assert repair_json(" ") == ""
    assert repair_json("string") == ""
    assert repair_json("stringbeforeobject {}") == "{}"


def test_missing_and_mixed_quotes():
    assert (
        repair_json("{'key': 'string', 'key2': false, \"key3\": null, \"key4\": unquoted}")
        == '{"key": "string", "key2": false, "key3": null, "key4": "unquoted"}'
    )
    assert (
        repair_json('{"name": "John", "age": 30, "city": "New York')
        == '{"name": "John", "age": 30, "city": "New York"}'
    )
    assert (
        repair_json('{"name": "John", "age": 30, city: "New York"}')
        == '{"name": "John", "age": 30, "city": "New York"}'
    )
    assert (
        repair_json('{"name": "John", "age": 30, "city": New York}')
        == '{"name": "John", "age": 30, "city": "New York"}'
    )
    assert (
        repair_json('{"name": John, "age": 30, "city": "New York"}')
        == '{"name": "John", "age": 30, "city": "New York"}'
    )
    assert repair_json('{“slanted_delimiter”: "value"}') == '{"slanted_delimiter": "value"}'
    assert repair_json('{"name": "John", "age": 30, "city": "New') == '{"name": "John", "age": 30, "city": "New"}'
    assert (
        repair_json('{"name": "John", "age": 30, "city": "New York, "gender": "male"}')
        == '{"name": "John", "age": 30, "city": "New York", "gender": "male"}'
    )

    assert (
        repair_json('[{"key": "value", COMMENT "notes": "lorem "ipsum", sic." }]')
        == '[{"key": "value", "notes": "lorem \\"ipsum\\", sic."}]'
    )
    assert repair_json('{"key": ""value"}') == '{"key": "value"}'
    assert repair_json('{"key": "value", 5: "value"}') == '{"key": "value", "5": "value"}'
    assert repair_json('{"foo": "\\"bar\\""') == '{"foo": "\\"bar\\""}'
    assert repair_json('{"" key":"val"') == '{" key": "val"}'
    assert repair_json('{"key": value "key2" : "value2" ') == '{"key": "value", "key2": "value2"}'
    assert (
        repair_json('{"key": "lorem ipsum ... "sic " tamet. ...}') == '{"key": "lorem ipsum ... \\"sic \\" tamet. ..."}'
    )
    assert repair_json('{"key": value , }') == '{"key": "value"}'
    assert (
        repair_json('{"comment": "lorem, "ipsum" sic "tamet". To improve"}')
        == '{"comment": "lorem, \\"ipsum\\" sic \\"tamet\\". To improve"}'
    )
    assert repair_json('{"key": "v"alu"e"} key:') == '{"key": "v\\"alu\\"e"}'
    assert repair_json('{"key": "v"alue", "key2": "value2"}') == '{"key": "v\\"alue", "key2": "value2"}'
    assert repair_json('[{"key": "v"alu,e", "key2": "value2"}]') == '[{"key": "v\\"alu,e", "key2": "value2"}]'


def test_escaping():
    assert repair_json("'\"'") == ""
    assert repair_json('{"key": \'string"\n\t\\le\'') == '{"key": "string\\"\\n\\t\\\\le"}'
    assert (
        repair_json(
            r'{"real_content": "Some string: Some other string \t Some string <a href=\"https://domain.com\">Some link</a>"'
        )
        == r'{"real_content": "Some string: Some other string \t Some string <a href=\"https://domain.com\">Some link</a>"}'
    )
    assert repair_json('{"key_1\n": "value"}') == '{"key_1": "value"}'
    assert repair_json('{"key\t_": "value"}') == '{"key\\t_": "value"}'
    assert repair_json("{\"key\": '\u0076\u0061\u006c\u0075\u0065'}") == '{"key": "value"}'
    assert repair_json('{"key": "\\u0076\\u0061\\u006C\\u0075\\u0065"}', skip_json_loads=True) == '{"key": "value"}'
    assert repair_json("""{"key": "valu\\'e"}""") == """{"key": "valu'e"}"""
    assert repair_json('{\'key\': "{\\"key\\": 1, \\"key2\\": 1}"}') == '{"key": "{\\"key\\": 1, \\"key2\\": 1}"}'


def test_markdown():
    assert (
        repair_json('{ "content": "[LINK]("https://google.com")" }')
        == '{"content": "[LINK](\\"https://google.com\\")"}'
    )
    assert repair_json('{ "content": "[LINK](" }') == '{"content": "[LINK]("}'
    assert repair_json('{ "content": "[LINK](", "key": true }') == '{"content": "[LINK](", "key": true}'


def test_leading_trailing_characters():
    assert repair_json('````{ "key": "value" }```') == '{"key": "value"}'
    assert repair_json("""{    "a": "",    "b": [ { "c": 1} ] \n}```""") == '{"a": "", "b": [{"c": 1}]}'
    assert (
        repair_json("Based on the information extracted, here is the filled JSON output: ```json { 'a': 'b' } ```")
        == '{"a": "b"}'
    )
    assert (
        repair_json("""
                       The next 64 elements are:
                       ```json
                       { "key": "value" }
                       ```""")
        == '{"key": "value"}'
    )


def test_fenced_json_wrapper_matches_plain_for_duplicate_keys():
    fenced = """
    ```json
    {
    "k": [
    {
    "b":"v2",
    "b":"v2"
    }
    ]
    }
    ```
    """
    plain = """
    {
    "k": [
    {
    "b":"v2",
    "b":"v2"
    }
    ]
    }
    """
    assert repair_json(fenced, return_objects=True) == repair_json(plain, return_objects=True)


def test_string_json_llm_block():
    assert repair_json('{"key": "``"') == '{"key": "``"}'
    assert repair_json('{"key": "```json"') == '{"key": "```json"}'
    assert (
        repair_json('{"key": "```json {"key": [{"key1": 1},{"key2": 2}]}```"}')
        == '{"key": {"key": [{"key1": 1}, {"key2": 2}]}}'
    )
    assert repair_json('{"response": "```json{}"') == '{"response": "```json{}"}'


def test_parse_string_logs_invalid_code_fences():
    repaired, logs = repair_json('{"key": "```json nope\\n"}', skip_json_loads=True, return_objects=True, logging=True)
    assert repaired == {"key": "```json nope"}
    assert any("did not enclose valid JSON" in log["text"] for log in logs)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('{\n"a": "\n```{}```\n",\n"b": "x",\n}', {"a": "\n```{}```", "b": "x"}),
        ('{\n"a": "\n```{}```\n"\n",\n"b": "x",\n}', {"a": '\n```{}```\n"', "b": "x"}),
        ('{\n"a": "\n```{}```\n"\n",\n\'b\': "x",\n}', {"a": '\n```{}```\n"', "b": "x"}),
        ('{\n"a": "\n```{}```\n"\n", // c\n"b": "x",\n}', {"a": '\n```{}```\n"', "b": "x"}),
        ('{\n"a": "\n```{}```\n"\n",\n b: "x",\n}', {"a": '\n```{}```\n"', "b": "x"}),
        ('{"a":"```}```"a","b":"x"}', {"a": '```}```"a', "b": "x"}),
        ('{"a":"x}``` [1,2]\n","b":"y"}', {"a": "x}``` [1,2]", "b": "y"}),
        ('{"a":"x}``` [http://x]\n","b":"y"}', {"a": "x}``` [http://x]", "b": "y"}),
        ('{"a":"x}``` [foo[bar]\n","b":"y"}', {"a": "x}``` [foo[bar]", "b": "y"}),
        ('{"a":"x}``` [{\n","b":"y"}', {"a": "x}``` [{", "b": "y"}),
        ('{"a":"x}``` [foo, [bar]\n","b":"y"}', {"a": "x}``` [foo, [bar]", "b": "y"}),
        ('{"a":"x}``` [1,"z"]\n","b":"y"}', {"a": 'x}``` [1,"z"]', "b": "y"}),
        ('{"a":"x}``` [1, [2]]\n","b":"y"}', {"a": "x}``` [1, [2]]", "b": "y"}),
        ('{"a":"x}``` [1,[2],k:v]\n","b":"y"}', {"a": "x}``` [1,[2],k:v]", "b": "y"}),
        ('{"a":"x}``` (1,(2),k:v)\n","b":"y"}', {"a": "x}``` (1,(2),k:v)", "b": "y"}),
        ('{"a":"x}``` [1,2],\n","b":"y"}', {"a": "x}``` [1,2],", "b": "y"}),
        ('{"a":"x}``` // c\n [1,2]\n","b":"y"}', {"a": "x}``` // c\n [1,2]", "b": "y"}),
        ('{"a":"x}``` // c\n [1,2],\n","b":"y"}', {"a": "x}``` // c\n [1,2],", "b": "y"}),
        (
            '{\n"a": "\n```c\nint main() {\n}\n```\nImplementation: "xxx", xxx\n",\n"b": "x",\n}',
            {"a": '\n```c\nint main() {\n}\n```\nImplementation: "xxx", xxx', "b": "x"},
        ),
    ],
    ids=[
        "multiline-object-value",
        "stray-quote-line",
        "single-quoted-next-key",
        "comment-prefixed-next-key",
        "bare-next-key",
        "inline-quoted-prose",
        "inline-array-literal",
        "url-like-inline-array",
        "unmatched-inner-delimiter",
        "unbalanced-inline-array-like-prose",
        "unmatched-inner-delimiter-after-comma",
        "quoted-item-inline-array",
        "balanced-nested-inline-array",
        "nested-numeric-inline-array-with-bare-key-like-prose",
        "nested-numeric-parenthesized-value-with-bare-key-like-prose",
        "inline-array-with-trailing-comma",
        "comment-prefixed-inline-array",
        "comment-prefixed-inline-array-with-trailing-comma",
        "fenced-code-block-before-inline-quoted-prose",
    ],
)
def test_parse_string_keeps_literal_fenced_snippet_cases(raw, expected):
    _assert_object_repairs(raw, expected)


def test_parse_string_stray_quote_line_before_trailing_comma_drops_stray_quote():
    _assert_object_repairs('{"a": "hello\n"\n",}', {"a": "hello"})


def test_parse_string_stray_quote_line_before_trailing_comma_at_eof_drops_stray_quote():
    _assert_object_repairs('{"a": "hello\n"\n",', {"a": "hello"})


def test_parse_string_keeps_multiline_curly_quoted_prose_after_comma():
    _assert_object_repairs('{"x": "a,\n “term”: explanation", "y": 2}', {"x": "a,\n “term”: explanation", "y": 2})


def test_parse_boolean_or_null():
    assert repair_json("True", return_objects=True) == ""
    assert repair_json("False", return_objects=True) == ""
    assert repair_json("Null", return_objects=True) == ""
    assert repair_json("true", return_objects=True)
    assert not repair_json("false", return_objects=True)
    assert repair_json("null", return_objects=True) is None
    assert repair_json('  {"key": true, "key2": false, "key3": null}') == '{"key": true, "key2": false, "key3": null}'
    assert repair_json('{"key": TRUE, "key2": FALSE, "key3": Null}   ') == '{"key": true, "key2": false, "key3": null}'


def test_parse_string_fast_path_keeps_clean_values_log_free():
    repaired, logs = repair_json('{"key": "value", "items": ["alpha", "beta"]}', return_objects=True, logging=True)
    assert repaired == {"key": "value", "items": ["alpha", "beta"]}
    assert logs == []


def test_parse_string_fast_path_falls_back_for_escapes_with_logs():
    repaired, logs = repair_json(
        '{"key": "\\u0076\\u0061\\u006C\\u0075\\u0065"}',
        skip_json_loads=True,
        return_objects=True,
        logging=True,
    )
    assert repaired == {"key": "value"}
    assert any(log["text"] == "Found a unicode escape sequence, normalizing it" for log in logs)


def test_parse_string_fast_path_rejects_ambiguous_top_level_trailing_text():
    parser = JSONParser('"value" trailing', None, False)
    assert _try_parse_simple_quoted_string(parser) is None


def test_parse_string_keeps_inline_object_literal_after_comma():
    raw = '{"x": "However, the provided user answer is {"blank_1": "music"}, which is not a plain string"}'
    expected = '{"x": "However, the provided user answer is {\\"blank_1\\": \\"music\\"}, which is not a plain string"}'

    assert repair_json(raw) == expected
    assert repair_json(raw, skip_json_loads=True) == expected


def test_parse_string_keeps_inline_object_literal_before_next_member():
    cases = [
        (
            '{"x": "a, {"k": 1}, "y": 2}',
            '{"x": "a, {\\"k\\": 1}", "y": 2}',
        ),
        (
            '{"x": "a, {"k": {"n": 1}}, "y": 2}',
            '{"x": "a, {\\"k\\": {\\"n\\": 1}}", "y": 2}',
        ),
    ]

    for raw, expected in cases:
        assert repair_json(raw) == expected
        assert repair_json(raw, skip_json_loads=True) == expected


def test_parse_string_object_value_brace_heuristics():
    cases = [
        ('{"key": "value}\\\\\\"more"}', {"key": 'value}"more'}),
        ('{"key": "value} "tail}', {"key": "value} "}),
        ('{"key": "value} "tail" more}', {"key": 'value} "tail" more'}),
        ('{"key": "value} key2: value2}', {"key": "value"}),
    ]

    for raw, expected in cases:
        assert repair_json(raw, return_objects=True, skip_json_loads=True) == expected


def test_parse_string_missing_quotes_object_value_stops_at_quote_fragment():
    assert repair_json('{0:a"0"', return_objects=True, skip_json_loads=True) == {"0": "a"}


def test_parse_string_fast_path_string_wrapper_fallbacks():
    escaped_parser = JSONParser("", None, False)
    escaped_parser.json_str = StringFileWrapper(StringIO('"va\\lue"'), 2)
    assert _try_parse_simple_quoted_string(escaped_parser) is None

    unterminated_parser = JSONParser("", None, False)
    unterminated_parser.json_str = StringFileWrapper(StringIO('"value'), 2)
    assert _try_parse_simple_quoted_string(unterminated_parser) is None


def test_brace_before_code_fence_helper_rejects_non_delimiter_after_quote():
    parser = JSONParser('}```"oops', None, False)
    assert not _brace_before_code_fence_belongs_to_string(parser, StringParseState(), 1)


def test_brace_before_code_fence_helper_rejects_unterminated_container_after_fence():
    parser = JSONParser("}``` [1,2", None, False)
    assert not _brace_before_code_fence_belongs_to_string(parser, StringParseState(), 1)


def test_brace_before_code_fence_helper_accepts_unbalanced_container_like_prose_after_fence():
    parser = JSONParser('}``` [{\n", "b": 1', None, False)
    assert _brace_before_code_fence_belongs_to_string(parser, StringParseState(), 1)


def test_brace_before_code_fence_helper_accepts_later_closing_quote_after_quoted_prose():
    parser = JSONParser('}```Implementation: "xxx", xxx", "b": 1', None, False)
    assert _brace_before_code_fence_belongs_to_string(parser, StringParseState(), 1)


def test_brace_before_code_fence_helper_rejects_container_started_after_fence():
    parser = JSONParser('}``` [1,"z"], "b": 1', None, False)
    assert not _brace_before_code_fence_belongs_to_string(parser, StringParseState(), 1)


def test_brace_before_code_fence_helper_rejects_container_closing_object_after_fence():
    parser = JSONParser("}``` [1,2]}", None, False)
    assert not _brace_before_code_fence_belongs_to_string(parser, StringParseState(), 1)


def test_brace_before_code_fence_helper_accepts_literal_container_after_fence():
    parser = JSONParser('}``` [1,2]\n", "b": 1', None, False)
    assert _brace_before_code_fence_belongs_to_string(parser, StringParseState(), 1)


def test_brace_before_code_fence_helper_rejects_comment_prefixed_container_after_fence():
    parser = JSONParser('}``` // c\n [1,"z"], "b": 1', None, False)
    assert not _brace_before_code_fence_belongs_to_string(parser, StringParseState(), 1)


def test_brace_before_code_fence_helper_accepts_comment_prefixed_literal_container_after_fence():
    parser = JSONParser('}``` // c\n [1,2]\n", "b": 1', None, False)
    assert _brace_before_code_fence_belongs_to_string(parser, StringParseState(), 1)


def test_brace_before_code_fence_helper_accepts_literal_container_after_fence_with_trailing_comma():
    parser = JSONParser('}``` [1,2],\n", "b": 1', None, False)
    assert _brace_before_code_fence_belongs_to_string(parser, StringParseState(), 1)


def test_brace_before_code_fence_helper_accepts_comment_prefixed_literal_container_after_fence_with_trailing_comma():
    parser = JSONParser('}``` // c\n [1,2],\n", "b": 1', None, False)
    assert _brace_before_code_fence_belongs_to_string(parser, StringParseState(), 1)


def test_skip_inline_container_returns_same_index_for_non_container():
    parser = JSONParser("text", None, False)
    assert _skip_inline_container(parser, 0) == 0


def test_starts_nested_inline_container_accepts_container_at_start():
    parser = JSONParser("[1, 2]", None, False)
    assert _starts_nested_inline_container(parser, 0)


def test_starts_nested_inline_container_accepts_out_of_range_prefix_conservatively():
    parser = JSONParser("[1, 2]", None, False)
    assert _starts_nested_inline_container(parser, 10)


def test_starts_nested_inline_container_rejects_unmatched_inner_array_after_comma():
    parser = JSONParser("[foo, [bar]", None, False)
    assert not _starts_nested_inline_container(parser, 6)


def test_starts_nested_inline_container_accepts_object_with_quoted_key_after_comma():
    parser = JSONParser('[foo, {"k": 1}]', None, False)
    assert _starts_nested_inline_container(parser, 6)


def test_starts_nested_inline_container_accepts_numeric_array_after_comma():
    parser = JSONParser("[foo, [2]]", None, False)
    assert _starts_nested_inline_container(parser, 6)


def test_starts_nested_inline_container_accepts_numeric_parenthesized_value_after_comma():
    parser = JSONParser("(foo, (2))", None, False)
    assert _starts_nested_inline_container(parser, 6)


def test_starts_nested_inline_container_accepts_object_with_bare_key_after_colon():
    parser = JSONParser("{foo: {bar: 1}}", None, False)
    assert _starts_nested_inline_container(parser, 6)


def test_starts_nested_inline_container_rejects_object_with_bare_key_after_comma():
    parser = JSONParser("[foo, {bar}]", None, False)
    assert not _starts_nested_inline_container(parser, 6)


def test_starts_nested_inline_container_rejects_non_container_after_separator():
    parser = JSONParser("[foo, xbar]", None, False)
    assert not _starts_nested_inline_container(parser, 6)


def test_starts_nested_inline_container_rejects_object_with_non_key_start_after_colon():
    parser = JSONParser("{foo: {-bar}}", None, False)
    assert not _starts_nested_inline_container(parser, 6)


def test_skip_inline_container_skips_nested_inline_container():
    parser = JSONParser("[{items: [1, 2]}] tail", None, False)
    assert _skip_inline_container(parser, 0) == 17


def test_skip_inline_container_keeps_hash_like_literal_content():
    parser = JSONParser("[# literal] tail", None, False)
    assert _skip_inline_container(parser, 0) == 11


def test_skip_inline_container_keeps_line_comment_like_literal_content():
    parser = JSONParser("[http://x] tail", None, False)
    assert _skip_inline_container(parser, 0) == 10


def test_skip_inline_container_keeps_block_comment_like_literal_content():
    parser = JSONParser("[a/*b*/c] tail", None, False)
    assert _skip_inline_container(parser, 0) == 9


def test_skip_inline_container_keeps_regex_like_literal_content():
    parser = JSONParser("[/a//b/] tail", None, False)
    assert _skip_inline_container(parser, 0) == 8


def test_skip_inline_container_keeps_unmatched_inner_delimiter_as_literal_content():
    parser = JSONParser("[foo[bar] tail", None, False)
    assert _skip_inline_container(parser, 0) == 9


def test_skip_inline_container_rejects_unterminated_container():
    parser = JSONParser("[1, 2", None, False)
    assert _skip_inline_container(parser, 0) is None


def test_skip_inline_container_rejects_unterminated_string_inside_container():
    parser = JSONParser('["unterminated', None, False)
    assert _skip_inline_container(parser, 0) is None


def test_skip_inline_container_rejects_unterminated_block_comment():
    parser = JSONParser("[/* c", None, False)
    assert _skip_inline_container(parser, 0) is None


def test_update_inline_container_stack_starts_tracking_pending_container():
    inline_container_stack: list[str] = []
    pending_inline_container, keep_inline_container_char = update_inline_container_stack(
        "[", True, inline_container_stack
    )

    assert not pending_inline_container
    assert not keep_inline_container_char
    assert inline_container_stack == ["["]


def test_update_inline_container_stack_tracks_nested_container():
    inline_container_stack = ["["]
    pending_inline_container, keep_inline_container_char = update_inline_container_stack(
        "{", False, inline_container_stack
    )

    assert not pending_inline_container
    assert not keep_inline_container_char
    assert inline_container_stack == ["[", "{"]


def test_update_inline_container_stack_keeps_closing_container_character():
    inline_container_stack = ["["]
    pending_inline_container, keep_inline_container_char = update_inline_container_stack(
        "]", False, inline_container_stack
    )

    assert not pending_inline_container
    assert keep_inline_container_char
    assert inline_container_stack == []


def test_scan_string_body_keeps_closing_inline_container_character():
    parser = JSONParser(']"', None, False)
    parser.context.set(ContextValues.OBJECT_VALUE)
    state = StringParseState(string_acc="x", inline_container_stack=["["])

    char = _scan_string_body(parser, state)

    assert char == '"'
    assert state.string_acc == "x]"
    assert state.inline_container_stack == []


def test_quoted_object_member_follows_rejects_unquoted_next_key():
    parser = JSONParser('"\n", bare', None, False)
    assert not _quoted_object_member_follows(parser, 2)


def test_quoted_object_member_follows_rejects_unterminated_next_key():
    parser = JSONParser('"\n", "unterminated', None, False)
    assert not _quoted_object_member_follows(parser, 2)


def test_quoted_object_member_follows_accepts_single_quoted_next_key():
    parser = JSONParser("\"\n\", 'b': 1", None, False)
    assert _quoted_object_member_follows(parser, 2)


def test_quoted_object_member_follows_accepts_curly_quoted_next_key():
    parser = JSONParser('"\n", “b”: 1', None, False)
    assert _quoted_object_member_follows(parser, 2)


def test_quoted_object_member_follows_accepts_comment_before_next_key():
    parser = JSONParser('"\n", // c\n"b": 1', None, False)
    assert _quoted_object_member_follows(parser, 2)


def test_quoted_object_member_follows_accepts_hash_comment_before_next_key():
    parser = JSONParser('"\n", # c\n"b": 1', None, False)
    assert _quoted_object_member_follows(parser, 2)


def test_quoted_object_member_follows_accepts_block_comment_before_next_key():
    parser = JSONParser('"\n", /* c */ "b": 1', None, False)
    assert _quoted_object_member_follows(parser, 2)


def test_quoted_object_member_follows_accepts_comment_before_bare_next_key():
    parser = JSONParser('"\n", // c\n b: 1', None, False)
    assert _quoted_object_member_follows(parser, 2)


def test_quoted_object_member_follows_accepts_bare_next_key():
    parser = JSONParser('"\n",\n b: 1', None, False)
    assert _quoted_object_member_follows(parser, 2)


def test_quoted_object_member_follows_rejects_trailing_comma_endings():
    assert not _quoted_object_member_follows(JSONParser('"\n",}', None, False), 2)
    assert not _quoted_object_member_follows(JSONParser('"\n",', None, False), 2)


def test_quoted_object_member_follows_rejects_unclosed_block_comment_before_next_key():
    parser = JSONParser('"\n", /* c', None, False)
    assert not _quoted_object_member_follows(parser, 2)


def test_quoted_object_member_follows_rejects_array_after_comment():
    parser = JSONParser('"\n", /* c */ [1, 2]', None, False)
    assert not _quoted_object_member_follows(parser, 2)


def test_parse_string_empty_single_quoted_key():
    assert repair_json("{'': 1}") == '{"": 1}'
