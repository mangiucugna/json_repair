from io import StringIO

from src.json_repair.json_parser import JSONParser
from src.json_repair.json_repair import repair_json
from src.json_repair.parse_string import _try_parse_simple_quoted_string
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


def test_whitespace_only_strings():
    # By default trailing whitespace in values is stripped
    assert repair_json('{"test": "\n"}') == '{"test": ""}'
    assert repair_json('{"test": "hello\n"}') == '{"test": "hello"}'
    # With remove_string_whitespace=False, whitespace-only string values are preserved
    assert repair_json('{"test": "\n"}', remove_string_whitespace=False) == '{"test": "\\n"}'
    assert repair_json('{"test": "\t"}', remove_string_whitespace=False) == '{"test": "\\t"}'
    assert repair_json('{"test": " "}', remove_string_whitespace=False) == '{"test": " "}'
    assert repair_json('{"test": "  \n\t  "}', remove_string_whitespace=False) == '{"test": "  \\n\\t  "}'
    # Mixed content with leading/trailing whitespace is also preserved when opting out
    assert repair_json('{"test": "\n-"}', remove_string_whitespace=False) == '{"test": "\\n-"}'
    # Keys with trailing newlines are always stripped regardless of the parameter
    assert repair_json('{"key_1\n": "value"}') == '{"key_1": "value"}'
    assert repair_json('{"key_1\n": "value"}', remove_string_whitespace=False) == '{"key_1": "value"}'


def test_remove_string_whitespace():
    # remove_string_whitespace=True (default) strips trailing whitespace from values
    assert repair_json('{"test": "\n"}', remove_string_whitespace=True) == '{"test": ""}'
    assert repair_json('{"test": "hello\n"}', remove_string_whitespace=True) == '{"test": "hello"}'
    # A value that ends with \n (after other whitespace) is also stripped
    assert repair_json('{"test": "hello \n"}', remove_string_whitespace=True) == '{"test": "hello"}'
    # Values not ending with \n are unaffected (stripping only applies to a trailing newline)
    assert repair_json('{"test": "  \n\t  "}', remove_string_whitespace=True) == '{"test": "  \\n\\t  "}'
    # remove_string_whitespace=False preserves trailing whitespace in values
    assert repair_json('{"test": "\n"}', remove_string_whitespace=False) == '{"test": "\\n"}'
    assert repair_json('{"test": "hello\n"}', remove_string_whitespace=False) == '{"test": "hello\\n"}'


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
    # By default trailing \n is stripped (remove_string_whitespace=True)
    assert repaired == {"key": "```json nope"}
    assert any("did not enclose valid JSON" in log["text"] for log in logs)
    # With remove_string_whitespace=False the trailing \n is preserved
    repaired_kept, _ = repair_json(
        '{"key": "```json nope\\n"}',
        skip_json_loads=True,
        return_objects=True,
        logging=True,
        remove_string_whitespace=False,
    )
    assert repaired_kept == {"key": "```json nope\n"}


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


def test_parse_string_fast_path_string_wrapper_fallbacks():
    escaped_parser = JSONParser("", None, False)
    escaped_parser.json_str = StringFileWrapper(StringIO('"va\\lue"'), 2)
    assert _try_parse_simple_quoted_string(escaped_parser) is None

    unterminated_parser = JSONParser("", None, False)
    unterminated_parser.json_str = StringFileWrapper(StringIO('"value'), 2)
    assert _try_parse_simple_quoted_string(unterminated_parser) is None


def test_parse_string_empty_single_quoted_key():
    assert repair_json("{'': 1}") == '{"": 1}'
