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
from tests.utils.string_cases import FENCED_SNIPPET_CASES, FENCED_SNIPPET_IDS


def _assert_object_repairs(raw: str, expected: dict) -> None:
    assert repair_json(raw, return_objects=True) == expected
    assert repair_json(raw, skip_json_loads=True, return_objects=True) == expected


class CountingParser(JSONParser):
    def __init__(self, json_str: str) -> None:
        super().__init__(json_str, None, False)
        self.skip_to_character_calls = 0

    def skip_to_character(self, character: str | list[str], idx: int = 0) -> int:
        self.skip_to_character_calls += 1
        return super().skip_to_character(character, idx)


def test_parse_string() -> None:
    assert repair_json('"') == ""
    assert repair_json("\n") == ""
    assert repair_json(" ") == ""
    assert repair_json("string") == ""
    assert repair_json("stringbeforeobject {}") == "{}"


def test_missing_and_mixed_quotes() -> None:
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


@pytest.mark.parametrize("strict", [False, True])
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('{"title": ""hello" world"}', {"title": '"hello" world'}),
        ('{"title": ""hello" world", "b": "y"}', {"title": '"hello" world', "b": "y"}),
    ],
)
def test_parse_string_preserves_leading_quoted_phrase(raw: str, expected: object, strict: bool) -> None:
    assert repair_json(raw, return_objects=True, strict=strict) == expected


@pytest.mark.parametrize("strict", [False, True])
def test_parse_string_removes_redundant_leading_quote(strict: bool) -> None:
    assert repair_json('{"key": ""value"}', return_objects=True, strict=strict) == {"key": "value"}


def test_object_value_comma_without_future_delimiter_scans_once() -> None:
    parser = CountingParser('"value,fragment,fragment,fragment')
    parser.context.set(ContextValues.OBJECT_VALUE)

    assert parser.parse_string() == "value,fragment,fragment,fragment"
    assert parser.skip_to_character_calls == 1


def test_object_value_bare_key_prose_scans_once() -> None:
    raw = '"value\\n' + (", floof: prose" * 100) + '"'
    parser = CountingParser(raw)
    parser.context.set(ContextValues.OBJECT_VALUE)

    assert parser.parse_string() == "value\n" + (", floof: prose" * 100)
    assert parser.skip_to_character_calls == 3


def test_parse_string_keeps_colon_prose_inside_wrapped_valid_json() -> None:
    raw = r"""Here's your JSON:
{
  "stuff": [
    {
      "a": "foo",
      "blist": [
        {
          "text": "a\n b c, floof: a\n ... a b (c), floof: \n a",
          "id": 8
        }
      ]
    }
  ]
}
"""
    expected = {
        "stuff": [
            {
                "a": "foo",
                "blist": [{"text": "a\n b c, floof: a\n ... a b (c), floof: \n a", "id": 8}],
            }
        ]
    }

    _assert_object_repairs(raw, expected)
    repaired, logs = repair_json(raw, return_objects=True, logging=True)
    assert repaired == expected
    assert not any("comma that starts the next object member" in log["text"] for log in logs)


def test_parse_string_keeps_code_like_content_inside_valid_json() -> None:
    raw = r'{"command":"x\nrollback: (registry: Registry, snapshot: EntitySnapshot) => void;"}'
    expected = {"command": "x\nrollback: (registry: Registry, snapshot: EntitySnapshot) => void;"}

    _assert_object_repairs(raw, expected)
    repaired, logs = repair_json(raw, skip_json_loads=True, return_objects=True, logging=True)
    assert repaired == expected
    assert not any("comma that starts the next object member" in log["text"] for log in logs)


def test_parse_string_keeps_pseudo_object_code_inside_valid_json() -> None:
    raw = r'{"command":"x\nrollback: {registry: Registry, snapshot: EntitySnapshot}"}'
    expected = {"command": "x\nrollback: {registry: Registry, snapshot: EntitySnapshot}"}

    _assert_object_repairs(raw, expected)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('{"a": "first, b: "second"}', {"a": "first", "b": "second"}),
        ('{"a": "first, b: 1}', {"a": "first", "b": 1}),
        ('{"a": "first, b: true}', {"a": "first", "b": True}),
        ('{"a": "first, b: [1]}', {"a": "first", "b": [1]}),
        ('{"a": "first, b: prose}', {"a": "first", "b": "prose"}),
    ],
)
def test_parse_string_keeps_bare_member_recovery_for_explicit_and_unclosed_values(raw: str, expected: object) -> None:
    assert repair_json(raw, skip_json_loads=True, return_objects=True) == expected


def test_escaping() -> None:
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


def test_markdown() -> None:
    assert (
        repair_json('{ "content": "[LINK]("https://google.com")" }')
        == '{"content": "[LINK](\\"https://google.com\\")"}'
    )
    assert repair_json('{ "content": "[LINK](" }') == '{"content": "[LINK]("}'
    assert repair_json('{ "content": "[LINK](", "key": true }') == '{"content": "[LINK](", "key": true}'


@pytest.mark.parametrize(
    "fenced",
    [False, True],
)
def test_parse_string_keeps_bare_quotes_inside_regex_character_classes(fenced: bool) -> None:
    raw = """{
        "results": [
            {"regex": "^\\s*path\\(\\s*['\"]([^'\"]+)['\"]\\s*,"},
            {"regex": "^\\s*re_path\\(\\s*[^'\"]+['\"]\\s*,"}
        ]
    }"""
    if fenced:
        raw = f"```json\n{raw}\n```"

    assert repair_json(raw, return_objects=True, skip_json_loads=True) == {
        "results": [
            {"regex": r"""^\s*path\(\s*['"]([^'"]+)['"]\s*,"""},
            {"regex": r"""^\s*re_path\(\s*[^'"]+['"]\s*,"""},
        ]
    }


@pytest.mark.parametrize(
    ("raw", "expected", "inside_class"),
    [
        (r'{"a":"\u005bx"z] tail", "b":1}', '[x"z] tail', True),
        (r'{"a":"[x\u005dy"z] tail", "b":1}', '[x]y"z] tail', False),
    ],
)
def test_unicode_escaped_brackets_update_regex_class_state(raw: str, expected: str, inside_class: bool) -> None:
    result, logs = repair_json(raw, return_objects=True, skip_json_loads=True, logging=True)

    assert result == {"a": expected, "b": 1}
    assert any("bare quote inside a regex character class" in entry["text"] for entry in logs) is inside_class


def test_parse_string_still_closes_regular_object_members_after_quoted_values() -> None:
    assert repair_json('{"first": "value", "second": "next"}', return_objects=True, skip_json_loads=True) == {
        "first": "value",
        "second": "next",
    }


def test_leading_trailing_characters() -> None:
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


def test_fenced_json_wrapper_matches_plain_for_duplicate_keys() -> None:
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
    expected = {"k": [{"b": "v2"}]}
    assert repair_json(fenced, return_objects=True) == expected
    assert repair_json(plain, return_objects=True) == expected


def test_string_json_llm_block() -> None:
    assert repair_json('{"key": "``"') == '{"key": "``"}'
    assert repair_json('{"key": "```json"') == '{"key": "```json"}'
    assert (
        repair_json('{"key": "```json {"key": [{"key1": 1},{"key2": 2}]}```"}')
        == '{"key": {"key": [{"key1": 1}, {"key2": 2}]}}'
    )
    assert repair_json('{"response": "```json{}"') == '{"response": "```json{}"}'


def test_parse_string_logs_invalid_code_fences() -> None:
    repaired, logs = repair_json('{"key": "```json nope\\n"}', skip_json_loads=True, return_objects=True, logging=True)
    assert repaired == {"key": "```json nope"}
    assert any("did not enclose valid JSON" in log["text"] for log in logs)


@pytest.mark.parametrize(("raw", "expected"), FENCED_SNIPPET_CASES, ids=FENCED_SNIPPET_IDS)
def test_parse_string_keeps_literal_fenced_snippet_cases(raw: str, expected: dict) -> None:
    _assert_object_repairs(raw, expected)


def test_parse_string_stray_quote_line_before_trailing_comma_drops_stray_quote() -> None:
    _assert_object_repairs('{"a": "hello\n"\n",}', {"a": "hello"})


def test_parse_string_stray_quote_line_before_trailing_comma_at_eof_drops_stray_quote() -> None:
    _assert_object_repairs('{"a": "hello\n"\n",', {"a": "hello"})


def test_parse_string_keeps_multiline_curly_quoted_prose_after_comma() -> None:
    _assert_object_repairs('{"x": "a,\n “term”: explanation", "y": 2}', {"x": "a,\n “term”: explanation", "y": 2})


def test_parse_string_keeps_low_smart_quote_span_closed_by_ascii_quote() -> None:
    _assert_object_repairs(
        '{"text": "despre „autocritică" și autocompasiune"}',
        {"text": 'despre „autocritică" și autocompasiune'},
    )


def test_parse_string_keeps_low_smart_quote_span_closed_by_unicode_quote() -> None:
    _assert_object_repairs(
        '{"text": "despre „autocritică” și autocompasiune"}',
        {"text": "despre „autocritică” și autocompasiune"},
    )


def test_parse_string_keeps_low_smart_quote_span_closed_by_escaped_ascii_quote() -> None:
    _assert_object_repairs(
        '{"text": "aplicație „sham\\"), a făcut"}',
        {"text": 'aplicație „sham"), a făcut'},
    )


def test_parse_string_escaped_low_smart_quote_does_not_open_inner_span() -> None:
    _assert_object_repairs(
        '{"text": "a \\„ b", "y": 1}',
        {"text": "a „ b", "y": 1},
    )


def test_parse_boolean_or_null() -> None:
    assert repair_json("True", return_objects=True) == ""
    assert repair_json("False", return_objects=True) == ""
    assert repair_json("Null", return_objects=True) == ""
    assert repair_json("true", return_objects=True) is True
    assert repair_json("false", return_objects=True) is False
    assert repair_json("null", return_objects=True) is None
    assert repair_json('  {"key": true, "key2": false, "key3": null}') == '{"key": true, "key2": false, "key3": null}'
    assert repair_json('{"key": TRUE, "key2": FALSE, "key3": Null}   ') == '{"key": true, "key2": false, "key3": null}'


def test_parse_literals_require_boundaries_and_support_python_none() -> None:
    assert repair_json('{"value": None }', return_objects=True) == {"value": None}
    assert repair_json("[None, TRUE, false, Null]", return_objects=True) == [None, True, False, None]
    assert repair_json("[None", return_objects=True) == [None]
    assert repair_json('{"value": "None"}', return_objects=True) == {"value": "None"}
    assert repair_json('{"value": none}', return_objects=True) == {"value": None}
    assert repair_json('{"value": NONE}', return_objects=True) == {"value": None}
    assert repair_json('{"value": trueblue}', return_objects=True) == {"value": "trueblue"}
    assert repair_json('{"value": falsehood}', return_objects=True) == {"value": "falsehood"}
    assert repair_json('{"value": nullify}', return_objects=True) == {"value": "nullify"}
    assert repair_json('{"value": NoneType}', return_objects=True) == {"value": "NoneType"}

    repaired, logs = repair_json('{"value": None}', return_objects=True, logging=True)
    assert repaired == {"value": None}
    assert any(log["text"] == "Converted unquoted Python None literal to JSON null" for log in logs)


def test_parse_string_fast_path_keeps_clean_values_log_free(monkeypatch: pytest.MonkeyPatch) -> None:
    successful_values: list[str] = []

    def track_fast_path(parser: JSONParser) -> str | None:
        value = _try_parse_simple_quoted_string(parser)
        if value is not None:
            successful_values.append(value)
        return value

    monkeypatch.setattr("src.json_repair.parse_string._try_parse_simple_quoted_string", track_fast_path)
    repaired, logs = repair_json(
        '{"key": "value", "items": ["alpha", "beta"]}',
        skip_json_loads=True,
        return_objects=True,
        logging=True,
    )
    assert repaired == {"key": "value", "items": ["alpha", "beta"]}
    assert logs == []
    assert "value" in successful_values


def test_parse_string_fast_path_falls_back_for_escapes_with_logs() -> None:
    repaired, logs = repair_json(
        '{"key": "\\u0076\\u0061\\u006C\\u0075\\u0065"}',
        skip_json_loads=True,
        return_objects=True,
        logging=True,
    )
    assert repaired == {"key": "value"}
    assert any(log["text"] == "Found a unicode escape sequence, normalizing it" for log in logs)


def test_parse_string_fast_path_rejects_ambiguous_top_level_trailing_text() -> None:
    parser = JSONParser('"value" trailing', None, False)
    assert _try_parse_simple_quoted_string(parser) is None


def test_parse_string_keeps_inline_object_literal_after_comma() -> None:
    raw = '{"x": "However, the provided user answer is {"blank_1": "music"}, which is not a plain string"}'
    expected = '{"x": "However, the provided user answer is {\\"blank_1\\": \\"music\\"}, which is not a plain string"}'

    assert repair_json(raw) == expected
    assert repair_json(raw, skip_json_loads=True) == expected


def test_parse_string_keeps_inline_object_literal_before_next_member() -> None:
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


def test_parse_string_object_value_brace_heuristics() -> None:
    cases = [
        ('{"key": "value}\\\\\\"more"}', {"key": 'value}"more'}),
        ('{"key": "value} "tail}', {"key": "value} "}),
        ('{"key": "value} "tail" more}', {"key": 'value} "tail" more'}),
        ('{"key": "value} key2: value2}', {"key": "value"}),
    ]

    for raw, expected in cases:
        assert repair_json(raw, return_objects=True, skip_json_loads=True) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (r'{"a":"\u007bvalue} key2: value2}', {"a": "{value} key2: value2"}),
        (r'{"a":"{x\u007d} key2: value2}', {"a": "{x}"}),
    ],
)
def test_unicode_escaped_braces_update_object_value_state(raw: str, expected: object) -> None:
    assert repair_json(raw, return_objects=True, skip_json_loads=True) == expected


def test_parse_string_far_quote_comma_payload_keeps_existing_repair_shape() -> None:
    raw = '{"a": "' + ("x," * 10_000) + '" tail'

    assert repair_json(raw, return_objects=True, skip_json_loads=True) == {"a": "x," * 10_000}


def test_parse_string_far_quote_brace_payload_keeps_existing_repair_shape() -> None:
    raw = '{"a": "' + ("x}" * 5_000) + '" tail'

    assert repair_json(raw, return_objects=True, skip_json_loads=True) == {"a": "x}" * 5_000}


def test_parse_string_preserves_escaped_braces_after_comma_group() -> None:
    raw = r'{ "key": "\\{1,2\\} \\{3\\}" }'

    assert repair_json(raw, return_objects=True, skip_json_loads=True) == {"key": r"\{1,2\} \{3\}"}


@pytest.mark.parametrize(
    ("raw", "expected", "serialized"),
    [
        (r'{"key": "a\\\\b\\\\c",}', r"a\\b\\c", r'{"key": "a\\\\b\\\\c"}'),
        (r'{"key": "1\\\\2\\\\3",}', r"1\\2\\3", r'{"key": "1\\\\2\\\\3"}'),
    ],
)
def test_parse_string_preserves_repeated_escaped_backslashes_during_repair(
    raw: str, expected: object, serialized: str
) -> None:
    for skip_json_loads in (False, True):
        assert repair_json(raw, return_objects=True, skip_json_loads=skip_json_loads) == {"key": expected}
        assert repair_json(raw, skip_json_loads=skip_json_loads) == serialized


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (r'{"path": "C:\\"', {"path": "C:\\"}),
        (r'["R\\"]', ["R\\"]),
        (r'["R\\\\"]', ["R\\\\"]),
    ],
)
def test_parse_string_preserves_backslashes_before_quote(raw: str, expected: object) -> None:
    assert repair_json(raw, return_objects=True, skip_json_loads=True) == expected


def test_parse_string_preserves_latex_command_after_bracketed_comma() -> None:
    raw = r'{ "key": "x [0,2] f(-\\frac{3}{4})" }'

    assert repair_json(raw, return_objects=True, skip_json_loads=True) == {"key": r"x [0,2] f(-\frac{3}{4})"}


def test_parse_string_keeps_latex_braces_before_inline_object_literal() -> None:
    raw = r'{ "llm_reason": "curve $C: \\frac{x^2}{m}$ answer is {"blank_1": "5"}, correct is 4.", "llm_answer": "4" }'

    assert repair_json(raw, return_objects=True, skip_json_loads=True) == {
        "llm_reason": r'curve $C: \frac{x^2}{m}$ answer is {"blank_1": "5"}, correct is 4.',
        "llm_answer": "4",
    }


def test_parse_string_missing_quotes_object_value_stops_at_quote_fragment() -> None:
    assert repair_json('{0:a"0"', return_objects=True, skip_json_loads=True) == {"0": "a"}


def test_parse_string_fast_path_string_wrapper_fallbacks() -> None:
    escaped_parser = JSONParser("", None, False)
    escaped_parser.json_str = StringFileWrapper(StringIO('"va\\lue"'), 2)
    assert _try_parse_simple_quoted_string(escaped_parser) is None

    unterminated_parser = JSONParser("", None, False)
    unterminated_parser.json_str = StringFileWrapper(StringIO('"value'), 2)
    assert _try_parse_simple_quoted_string(unterminated_parser) is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        pytest.param('}```"oops', False, id="rejects_non_delimiter_after_quote"),
        pytest.param("}``` [1,2", False, id="rejects_unterminated_container_after_fence"),
        pytest.param('}``` [{\n", "b": 1', True, id="accepts_unbalanced_container_like_prose_after_fence"),
        pytest.param(
            '}```Implementation: "xxx", xxx", "b": 1', True, id="accepts_later_closing_quote_after_quoted_prose"
        ),
        pytest.param('}``` [1,"z"], "b": 1', False, id="rejects_container_started_after_fence"),
        pytest.param("}``` [1,2]}", False, id="rejects_container_closing_object_after_fence"),
        pytest.param('}``` [1,2]\n", "b": 1', True, id="accepts_literal_container_after_fence"),
        pytest.param('}``` // c\n [1,"z"], "b": 1', False, id="rejects_comment_prefixed_container_after_fence"),
        pytest.param('}``` // c\n [1,2]\n", "b": 1', True, id="accepts_comment_prefixed_literal_container_after_fence"),
        pytest.param('}``` [1,2],\n", "b": 1', True, id="accepts_literal_container_after_fence_with_trailing_comma"),
        pytest.param(
            '}``` // c\n [1,2],\n", "b": 1',
            True,
            id="accepts_comment_prefixed_literal_container_after_fence_with_trailing_comma",
        ),
    ],
)
def test_brace_before_code_fence_belongs_to_string(raw: str, expected: bool) -> None:
    parser = JSONParser(raw, None, False)

    assert _brace_before_code_fence_belongs_to_string(parser, StringParseState(), 1) is expected


@pytest.mark.parametrize(
    ("raw", "index", "expected"),
    [
        pytest.param("text", 0, 0, id="returns_same_index_for_non_container"),
        pytest.param("[{items: [1, 2]}] tail", 0, 17, id="skips_nested_inline_container"),
        pytest.param("[# literal] tail", 0, 11, id="keeps_hash_like_literal_content"),
        pytest.param("[http://x] tail", 0, 10, id="keeps_line_comment_like_literal_content"),
        pytest.param("[a/*b*/c] tail", 0, 9, id="keeps_block_comment_like_literal_content"),
        pytest.param("[/a//b/] tail", 0, 8, id="keeps_regex_like_literal_content"),
        pytest.param("[foo[bar] tail", 0, 9, id="keeps_unmatched_inner_delimiter_as_literal_content"),
        pytest.param("[1, 2", 0, None, id="rejects_unterminated_container"),
        pytest.param('["unterminated', 0, None, id="rejects_unterminated_string_inside_container"),
        pytest.param("[/* c", 0, None, id="rejects_unterminated_block_comment"),
    ],
)
def test_skip_inline_container(raw: str, index: int, expected: int | None) -> None:
    parser = JSONParser(raw, None, False)

    assert _skip_inline_container(parser, index) == expected


@pytest.mark.parametrize(
    ("raw", "index", "expected"),
    [
        pytest.param("[1, 2]", 0, True, id="accepts_container_at_start"),
        pytest.param("[1, 2]", 10, True, id="accepts_out_of_range_prefix_conservatively"),
        pytest.param("[foo, [bar]", 6, False, id="rejects_unmatched_inner_array_after_comma"),
        pytest.param('[foo, {"k": 1}]', 6, True, id="accepts_object_with_quoted_key_after_comma"),
        pytest.param("[foo, [2]]", 6, True, id="accepts_numeric_array_after_comma"),
        pytest.param("(foo, (2))", 6, True, id="accepts_numeric_parenthesized_value_after_comma"),
        pytest.param("{foo: {bar: 1}}", 6, True, id="accepts_object_with_bare_key_after_colon"),
        pytest.param("[foo, {bar}]", 6, False, id="rejects_object_with_bare_key_after_comma"),
        pytest.param("[foo, xbar]", 6, False, id="rejects_non_container_after_separator"),
        pytest.param("{foo: {-bar}}", 6, False, id="rejects_object_with_non_key_start_after_colon"),
    ],
)
def test_starts_nested_inline_container(raw: str, index: int, expected: bool) -> None:
    parser = JSONParser(raw, None, False)

    assert _starts_nested_inline_container(parser, index) is expected


def test_update_inline_container_stack_starts_tracking_pending_container() -> None:
    inline_container_stack: list[str] = []
    pending_inline_container, keep_inline_container_char = update_inline_container_stack(
        "[", True, inline_container_stack
    )

    assert not pending_inline_container
    assert not keep_inline_container_char
    assert inline_container_stack == ["["]


def test_update_inline_container_stack_tracks_nested_container() -> None:
    inline_container_stack = ["["]
    pending_inline_container, keep_inline_container_char = update_inline_container_stack(
        "{", False, inline_container_stack
    )

    assert not pending_inline_container
    assert not keep_inline_container_char
    assert inline_container_stack == ["[", "{"]


def test_update_inline_container_stack_keeps_closing_container_character() -> None:
    inline_container_stack = ["["]
    pending_inline_container, keep_inline_container_char = update_inline_container_stack(
        "]", False, inline_container_stack
    )

    assert not pending_inline_container
    assert keep_inline_container_char
    assert inline_container_stack == []


def test_scan_string_body_keeps_closing_inline_container_character() -> None:
    parser = JSONParser(']"', None, False)
    parser.context.set(ContextValues.OBJECT_VALUE)
    state = StringParseState(string_acc="x", inline_container_stack=["["])

    char = _scan_string_body(parser, state)

    assert char == '"'
    assert state.string_acc == "x]"
    assert state.inline_container_stack == []


def test_scan_string_body_closes_low_smart_quote_span_with_unicode_quote() -> None:
    parser = JSONParser('”"', None, False)
    parser.context.set(ContextValues.OBJECT_VALUE)
    state = StringParseState(rstring_delimiter='"\0', string_acc="prefix")

    char = _scan_string_body(parser, state)

    assert char == '"'
    assert state.string_acc == "prefix”"
    assert state.rstring_delimiter == '"'


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        pytest.param('"\n", bare', False, id="rejects_unquoted_next_key"),
        pytest.param('"\n", "unterminated', False, id="rejects_unterminated_next_key"),
        pytest.param("\"\n\", 'b': 1", True, id="accepts_single_quoted_next_key"),
        pytest.param('"\n", “b”: 1', True, id="accepts_curly_quoted_next_key"),
        pytest.param('"\n", // c\n"b": 1', True, id="accepts_comment_before_next_key"),
        pytest.param('"\n", # c\n"b": 1', True, id="accepts_hash_comment_before_next_key"),
        pytest.param('"\n", /* c */ "b": 1', True, id="accepts_block_comment_before_next_key"),
        pytest.param('"\n", // c\n b: 1', True, id="accepts_comment_before_bare_next_key"),
        pytest.param('"\n",\n b: 1', True, id="accepts_bare_next_key"),
        pytest.param('"\n",}', False, id="rejects_trailing_comma_endings"),
        pytest.param('"\n",', False, id="rejects_trailing_comma_endings"),
        pytest.param('"\n", /* c', False, id="rejects_unclosed_block_comment_before_next_key"),
        pytest.param('"\n", /* c */ [1, 2]', False, id="rejects_array_after_comment"),
    ],
)
def test_quoted_object_member_follows(raw: str, expected: bool) -> None:
    parser = JSONParser(raw, None, False)

    assert _quoted_object_member_follows(parser, 2) is expected


def test_parse_string_empty_single_quoted_key() -> None:
    assert repair_json("{'': 1}") == '{"": 1}'
