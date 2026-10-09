import importlib
import sys

import pytest

from src.json_repair.json_parser import JSONParser
from src.json_repair.json_repair import loads, repair_json

json_repair_module = importlib.import_module("src.json_repair.json_repair")


@pytest.mark.parametrize("skip_json_loads", [False, True])
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('\n    "a": 1\n}\n', {"a": 1}),
        ('"a": 1, "b": 2}', {"a": 1, "b": 2}),
        ('"a": {"b": 2}}', {"a": {"b": 2}}),
        ('"a": [1, 2]}', {"a": [1, 2]}),
        ('"a": 0, "b": false, "c": null, "d": ""}', {"a": 0, "b": False, "c": None, "d": ""}),
        (r'"a\"b": "literal } and {"}', {'a"b': "literal } and {"}),
        ('"a:b": 1}', {"a:b": 1}),
        ('"a" \t\r\n: 1}', {"a": 1}),
        (r'"a\\": 1}', {"a\\": 1}),
    ],
)
def test_missing_opening_object_brace(raw, expected, skip_json_loads):
    assert loads(raw, skip_json_loads=skip_json_loads) == expected


def test_missing_opening_object_brace_logs_and_serializes():
    result = loads('"a": 1}', logging=True)
    assert isinstance(result, tuple)
    value, logs = result
    assert value == {"a": 1}
    assert any("opening" in entry["text"] and "brace" in entry["text"] for entry in logs)
    assert repair_json('"a": 1}') == '{"a": 1}'


@pytest.mark.parametrize("skip_json_loads", [False, True])
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('"a": 1', ""),
        ('"a": 1,}', ""),
        ('"a": 1}\v', ""),
        ('"a": {"b": 2}', {"b": 2}),
        ('"a": 1} {"b": 2}', {"b": 2}),
        ('Here is JSON: {"b": 2}', {"b": 2}),
        ("a: 1}", ""),
        ('"a', ""),
        ('"a" text', ""),
        ('"a"\v: 1}', ""),
        ("'a': 1}", ""),
        ("“a”: 1}", ""),
    ],
)
def test_missing_opening_brace_declines_other_malformed_inputs(raw, expected, skip_json_loads):
    result = loads(raw, logging=True, skip_json_loads=skip_json_loads)
    assert isinstance(result, tuple)
    value, logs = result
    assert value == expected
    assert not any("opening object brace" in entry["text"] for entry in logs)


def test_missing_opening_brace_declines_integer_conversion_limit():
    get_limit = getattr(sys, "get_int_max_str_digits", None)
    if get_limit is None or get_limit() == 0:
        pytest.skip("Python integer conversion limit is not enabled")
    raw = '"a": ' + "1" * (get_limit() + 1) + "}"
    assert loads(raw, logging=True) == ("", [])


def test_valid_top_level_string_preserved_with_strict_mode():
    assert loads('"a: 1}"', strict=True, logging=True) == ("a: 1}", [])
    assert loads('"a: 1}"', skip_json_loads=True, logging=True) == ("", [])


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("{}", {}),
        ("[]", []),
        ('"note"', ""),
        ('"unterminated', ""),
        ('"note" text', ""),
        ('"a": 1', ""),
    ],
)
def test_no_speculative_decode_without_missing_brace_signal(raw, expected, monkeypatch):
    def fail_raw_decode(*_args, **_kwargs):
        raise AssertionError(
            "ordinary fallback must not decode a speculative object without key, colon, and closing brace"
        )

    monkeypatch.setattr(json_repair_module.json.JSONDecoder, "raw_decode", fail_raw_decode)
    assert loads(raw, skip_json_loads=True) == expected


def test_valid_json():
    assert (
        repair_json('{"name": "John", "age": 30, "city": "New York"}')
        == '{"name": "John", "age": 30, "city": "New York"}'
    )
    assert repair_json('{"employees":["John", "Anna", "Peter"]} ') == '{"employees": ["John", "Anna", "Peter"]}'
    assert repair_json('{"key": "value:value"}') == '{"key": "value:value"}'
    assert repair_json('{"text": "The quick brown fox,"}') == '{"text": "The quick brown fox,"}'
    assert repair_json('{"text": "The quick brown fox won\'t jump"}') == '{"text": "The quick brown fox won\'t jump"}'
    assert repair_json('{"key": ""') == '{"key": ""}'
    assert repair_json('{"key1": {"key2": [1, 2, 3]}}') == '{"key1": {"key2": [1, 2, 3]}}'
    assert repair_json('{"key": 12345678901234567890}') == '{"key": 12345678901234567890}'
    assert repair_json('{"key": "value\u263a"}') == '{"key": "value\\u263a"}'
    assert repair_json('{"key": "value\\nvalue"}') == '{"key": "value\\nvalue"}'


def test_valid_json_fast_path_does_not_initialize_repair_parser(monkeypatch):
    def fail_parser_initialization(*_args, **_kwargs):
        raise AssertionError("valid JSON fast path should not initialize the repair parser")

    monkeypatch.setattr(json_repair_module, "JSONParser", fail_parser_initialization)

    assert json_repair_module.repair_json('{"key": "value"}', return_objects=True) == {"key": "value"}


def test_skip_json_loads_does_not_raw_decode_complete_json(monkeypatch):
    def fail_raw_decode(*_args, **_kwargs):
        raise AssertionError("skip_json_loads must not raw-decode complete JSON")

    monkeypatch.setattr(json_repair_module.json.JSONDecoder, "raw_decode", fail_raw_decode)

    assert repair_json('{"items": [1, 2, 3]}', return_objects=True, skip_json_loads=True) == {"items": [1, 2, 3]}


def test_prefixed_valid_json_uses_value_fast_path_when_json_loads_is_skipped(monkeypatch):
    raw = 'Here is your JSON:\n{"text": "a\\n b c, floof: a\\n ... a b (c), floof: \\n a", "id": 8}'
    expected = {"text": "a\n b c, floof: a\n ... a b (c), floof: \n a", "id": 8}
    original_try_parse = JSONParser._try_parse_valid_json_value
    value_attempts: list[int] = []

    def track_value_parse(self):
        value_attempts.append(self.index)
        return original_try_parse(self)

    monkeypatch.setattr(JSONParser, "_try_parse_valid_json_value", track_value_parse)

    assert repair_json(raw, return_objects=True) == expected
    assert value_attempts

    value_attempts.clear()

    def fail_json_loads(*_args, **_kwargs):
        raise AssertionError("skip_json_loads must not validate the whole input")

    monkeypatch.setattr(json_repair_module.json, "loads", fail_json_loads)
    assert repair_json(raw, return_objects=True, skip_json_loads=True) == expected
    assert value_attempts


def test_prefixed_valid_json_with_trailing_text_uses_value_fast_path(monkeypatch):
    def fail_parse_object(*_args, **_kwargs):
        raise AssertionError("raw decoding should avoid repair parsing")

    monkeypatch.setattr(JSONParser, "parse_object", fail_parse_object)

    raw = 'Here is your JSON:\n{"text": "literal } and ]"}\nAdditional explanation.'

    assert repair_json(raw, return_objects=True) == {"text": "literal } and ]"}


@pytest.mark.parametrize("skip_json_loads", [False, True])
def test_valid_json_with_trailing_garbage_preserves_string_content(skip_json_loads):
    raw = r"""{"tool_args": {"code": "# note\nconfig = {'type': 'object', 'properties': {}, 'additionalProperties': True}"}}}"""

    assert repair_json(raw, return_objects=True, skip_json_loads=skip_json_loads) == {
        "tool_args": {
            "code": "# note\nconfig = {'type': 'object', 'properties': {}, 'additionalProperties': True}",
        },
    }


def test_prefixed_invalid_json_falls_back_to_repair_parser():
    assert repair_json('Here is your JSON: {"key": "value', return_objects=True) == {"key": "value"}


def test_multiple_jsons():
    assert repair_json("[]{}") == "[]"
    assert repair_json('[]{"key":"value"}') == '{"key": "value"}'
    assert repair_json('{"key":"value"}[1,2,3,True]') == '[{"key": "value"}, [1, 2, 3, true]]'
    assert repair_json('{"key":"value"}, {"key":"value_after"}', return_objects=True) == [
        {"key": "value"},
        {"key": "value_after"},
    ]
    assert (
        repair_json('lorem ```json {"key":"value"} ``` ipsum ```json [1,2,3,True] ``` 42')
        == '[{"key": "value"}, [1, 2, 3, true]]'
    )
    assert repair_json('[{"key":"value"}][{"key":"value_after"}]') == '[{"key": "value_after"}]'


def test_top_level_separator_detects_pending_comma():
    parser = JSONParser(' , {"key": "value"}', None, False)

    assert parser._next_top_level_value_is_comma_separated()


def test_initial_container_trailing_content_rejects_mismatched_delimiters():
    parser = JSONParser("{]", None, False)

    assert parser._initial_container_has_non_comma_trailing_content() is False


def test_parenthesized_prose_does_not_hijack_fenced_json():
    assert (
        repair_json(
            """
         **Decision**: bla, bla (some clarification):

        ```json
        {
          "key": "value"
        }
        ```
        """
        )
        == '{"key": "value"}'
    )


def test_numbered_prose_line_does_not_hijack_fenced_json():
    assert (
        repair_json(
            """
        (1) Keep this note in the explanation.

        ```json
        {
          "key": "value"
        }
        ```
        """
        )
        == '{"key": "value"}'
    )


def test_parenthesized_tuple_still_parses_when_it_is_the_fenced_json_payload():
    assert repair_json(
        """
        Here is the tuple payload:

        ```json
        (1, 2)
        ```
        """,
        return_objects=True,
    ) == [1, 2]


def test_repair_json_with_objects():
    # Test with valid JSON strings
    assert repair_json("[]", return_objects=True) == []
    assert repair_json("{}", return_objects=True) == {}
    assert repair_json('{"key": true, "key2": false, "key3": null}', return_objects=True) == {
        "key": True,
        "key2": False,
        "key3": None,
    }
    assert repair_json('{"name": "John", "age": 30, "city": "New York"}', return_objects=True) == {
        "name": "John",
        "age": 30,
        "city": "New York",
    }
    assert repair_json("[1, 2, 3, 4]", return_objects=True) == [1, 2, 3, 4]
    assert repair_json('{"employees":["John", "Anna", "Peter"]} ', return_objects=True) == {
        "employees": ["John", "Anna", "Peter"]
    }
    assert repair_json(
        """
{
  "resourceType": "Bundle",
  "id": "1",
  "type": "collection",
  "entry": [
    {
      "resource": {
        "resourceType": "Patient",
        "id": "1",
        "name": [
          {"use": "official", "family": "Corwin", "given": ["Keisha", "Sunny"], "prefix": ["Mrs."},
          {"use": "maiden", "family": "Goodwin", "given": ["Keisha", "Sunny"], "prefix": ["Mrs."]}
        ]
      }
    }
  ]
}
""",
        return_objects=True,
    ) == {
        "resourceType": "Bundle",
        "id": "1",
        "type": "collection",
        "entry": [
            {
                "resource": {
                    "resourceType": "Patient",
                    "id": "1",
                    "name": [
                        {
                            "use": "official",
                            "family": "Corwin",
                            "given": ["Keisha", "Sunny"],
                            "prefix": ["Mrs."],
                        },
                        {
                            "use": "maiden",
                            "family": "Goodwin",
                            "given": ["Keisha", "Sunny"],
                            "prefix": ["Mrs."],
                        },
                    ],
                }
            }
        ],
    }
    assert repair_json(
        '{\n"html": "<h3 id="aaa">Waarom meer dan 200 Technical Experts - "Passie voor techniek"?</h3>"}',
        return_objects=True,
    ) == {"html": '<h3 id="aaa">Waarom meer dan 200 Technical Experts - "Passie voor techniek"?</h3>'}
    assert repair_json(
        """
        [
            {
                "foo": "Foo bar baz",
                "tag": "#foo-bar-baz"
            },
            {
                "foo": "foo bar "foobar" foo bar baz.",
                "tag": "#foo-bar-foobar"
            }
        ]
        """,
        return_objects=True,
    ) == [
        {"foo": "Foo bar baz", "tag": "#foo-bar-baz"},
        {"foo": 'foo bar "foobar" foo bar baz.', "tag": "#foo-bar-foobar"},
    ]


def test_repair_json_skip_json_loads():
    assert (
        repair_json('{"key": true, "key2": false, "key3": null}', skip_json_loads=True)
        == '{"key": true, "key2": false, "key3": null}'
    )
    assert repair_json(
        '{"key": true, "key2": false, "key3": null}',
        return_objects=True,
        skip_json_loads=True,
    ) == {"key": True, "key2": False, "key3": None}
    assert (
        repair_json('{"key": true, "key2": false, "key3": }', skip_json_loads=True)
        == '{"key": true, "key2": false, "key3": ""}'
    )
    assert loads('{"key": true, "key2": false, "key3": }', skip_json_loads=True) == {
        "key": True,
        "key2": False,
        "key3": "",
    }


def _nested_repair_payload(depth: int) -> str:
    return ("{a: [" * depth) + "1" + ("]}" * depth)


def _find_real_recursion_payload() -> str:
    depth = 1
    recursion_limit = sys.getrecursionlimit()

    while depth <= recursion_limit:
        payload = _nested_repair_payload(depth)
        try:
            JSONParser(payload, None, False).parse()
        except RecursionError:
            return payload
        depth *= 2

    pytest.skip("Could not reproduce parser recursion on this runtime.")
    raise AssertionError("pytest.skip() should raise an exception")


def test_repair_json_normalizes_real_parser_recursion_error():
    payload = _find_real_recursion_payload()

    with pytest.raises(ValueError, match="supported parser recursion depth"):
        repair_json(payload, return_objects=True)


def test_ensure_ascii():
    assert repair_json("{'test_中国人_ascii':'统一码'}", ensure_ascii=False) == '{"test_中国人_ascii": "统一码"}'


def test_stream_stable():
    # default: stream_stable = False
    # When the json to be repaired is the accumulation of streaming json at a certain moment.
    # The default repair result is unstable.
    assert repair_json('{"key": "val\\', stream_stable=False) == '{"key": "val\\\\"}'
    assert repair_json('{"key": "val\\n', stream_stable=False) == '{"key": "val"}'
    assert (
        repair_json('{"key": "val\\n123,`key2:value2', stream_stable=False) == '{"key": "val\\n123", "key2": "value2"}'
    )
    assert repair_json('{"key": "val\\n123,`key2:value2`"}', stream_stable=True) == '{"key": "val\\n123,`key2:value2`"}'
    # stream_stable = True
    assert repair_json('{"key": "val\\', stream_stable=True) == '{"key": "val"}'
    assert repair_json('{"key": "val\\n', stream_stable=True) == '{"key": "val\\n"}'
    assert repair_json('{"key": "val\\n123,`key2:value2', stream_stable=True) == '{"key": "val\\n123,`key2:value2"}'
    assert repair_json('{"key": "val\\n123,`key2:value2`"}', stream_stable=True) == '{"key": "val\\n123,`key2:value2`"}'


def test_logging():
    assert repair_json("{}", logging=True) == ({}, [])
    assert repair_json('{"key": "value}', logging=True) == (
        {"key": "value"},
        [
            {
                "context": 'y": "value}',
                "text": "While parsing a string missing the left delimiter in object value "
                "context, we found a , or } and we couldn't determine that a right "
                "delimiter was present. Stopping here",
            },
            {
                "context": 'y": "value}',
                "text": "While parsing a string, we missed the closing quote, ignoring",
            },
        ],
    )
