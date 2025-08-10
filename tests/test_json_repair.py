from src.json_repair.json_repair import loads, repair_json


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


def test_multiple_jsons():
    assert repair_json("[]{}") == "[[], {}]"
    assert repair_json("{}[]{}") == "[{}, [], {}]"
    assert repair_json('{"key":"value"}[1,2,3,True]') == '[{"key": "value"}, [1, 2, 3, true]]'
    assert (
        repair_json('lorem ```json {"key":"value"} ``` ipsum ```json [1,2,3,True] ``` 42')
        == '[{"key": "value"}, [1, 2, 3, true]]'
    )
    assert repair_json('[{"key":"value"}][{"key":"value_after"}]') == '[{"key": "value_after"}]'


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
