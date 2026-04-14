from io import StringIO

from src.json_repair.json_parser import JSONParser
from src.json_repair.json_repair import repair_json
from src.json_repair.parse_string import (
    StringParseState,
    _brace_before_code_fence_belongs_to_string,
    _quoted_object_member_follows,
    _try_parse_simple_quoted_string,
)
from src.json_repair.utils.string_file_wrapper import StringFileWrapper


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


def test_parse_string_keeps_literal_fenced_snippet_in_multiline_object_value():
    raw = '{\n"a": "\n```{}```\n",\n"b": "x",\n}'
    expected = {"a": "\n```{}```", "b": "x"}

    assert repair_json(raw, return_objects=True) == expected
    assert repair_json(raw, skip_json_loads=True, return_objects=True) == expected


def test_parse_string_keeps_literal_fenced_snippet_before_stray_quote_line():
    raw = '{\n"a": "\n```{}```\n"\n",\n"b": "x",\n}'
    expected = {"a": '\n```{}```\n"', "b": "x"}

    assert repair_json(raw, return_objects=True) == expected
    assert repair_json(raw, skip_json_loads=True, return_objects=True) == expected


def test_parse_string_keeps_literal_fenced_snippet_before_stray_quote_line_with_single_quoted_key():
    raw = '{\n"a": "\n```{}```\n"\n",\n\'b\': "x",\n}'
    expected = {"a": '\n```{}```\n"', "b": "x"}

    assert repair_json(raw, return_objects=True) == expected
    assert repair_json(raw, skip_json_loads=True, return_objects=True) == expected


def test_parse_string_keeps_literal_fenced_snippet_before_stray_quote_line_with_comment_before_key():
    raw = '{\n"a": "\n```{}```\n"\n", // c\n"b": "x",\n}'
    expected = {"a": '\n```{}```\n"', "b": "x"}

    assert repair_json(raw, return_objects=True) == expected
    assert repair_json(raw, skip_json_loads=True, return_objects=True) == expected


def test_parse_string_keeps_literal_fenced_snippet_before_stray_quote_line_with_bare_key():
    raw = '{\n"a": "\n```{}```\n"\n",\n b: "x",\n}'
    expected = {"a": '\n```{}```\n"', "b": "x"}

    assert repair_json(raw, return_objects=True) == expected
    assert repair_json(raw, skip_json_loads=True, return_objects=True) == expected


def test_parse_string_stray_quote_line_before_trailing_comma_drops_stray_quote():
    raw = '{"a": "hello\n"\n",}'
    expected = {"a": "hello"}

    assert repair_json(raw, return_objects=True) == expected
    assert repair_json(raw, skip_json_loads=True, return_objects=True) == expected


def test_parse_string_stray_quote_line_before_trailing_comma_at_eof_drops_stray_quote():
    raw = '{"a": "hello\n"\n",'
    expected = {"a": "hello"}

    assert repair_json(raw, return_objects=True) == expected
    assert repair_json(raw, skip_json_loads=True, return_objects=True) == expected


def test_parse_string_keeps_multiline_curly_quoted_prose_after_comma():
    raw = '{"x": "a,\n “term”: explanation", "y": 2}'
    expected = {"x": "a,\n “term”: explanation", "y": 2}

    assert repair_json(raw, return_objects=True) == expected
    assert repair_json(raw, skip_json_loads=True, return_objects=True) == expected


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
