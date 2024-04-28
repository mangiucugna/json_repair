from src.json_repair.json_repair import from_file, repair_json, loads


def test_repair_json():
    # Test with valid JSON strings
    assert repair_json("[]") == "[]"
    assert repair_json("   {  }   ") == "{}"
    assert repair_json("\"") == '""'
    assert repair_json("\n") == '""'
    assert repair_json('  {"key": true, "key2": false, "key3": null}') == '{"key": true, "key2": false, "key3": null}'
    assert repair_json('{"key": TRUE, "key2": FALSE, "key3": Null}   ') == '{"key": true, "key2": false, "key3": null}'
    assert repair_json("{'key': 'string', 'key2': false, \"key3\": null, \"key4\": unquoted}") == '{"key": "string", "key2": false, "key3": null, "key4": "unquoted"}'
    assert (
        repair_json('{"name": "John", "age": 30, "city": "New York"}')
        == '{"name": "John", "age": 30, "city": "New York"}'
    )
    assert repair_json("[1, 2, 3, 4]") == "[1, 2, 3, 4]"
    assert (
        repair_json('{"employees":["John", "Anna", "Peter"]} ')
        == '{"employees": ["John", "Anna", "Peter"]}'
    )

    # Test with invalid JSON strings
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
    assert repair_json("[1, 2, 3,") == "[1, 2, 3]"
    assert (
        repair_json('{"employees":["John", "Anna",')
        == '{"employees": ["John", "Anna"]}'
    )

    # Test with edge cases
    assert repair_json(" ") == '""'
    assert repair_json("[") == "[]"
    assert repair_json("]") == '""'
    assert repair_json("[[1\n\n]") == "[[1]]"
    assert repair_json("{") == "{}"
    assert repair_json("}") == '""'
    assert repair_json('{"') == '{}'
    assert repair_json('["') == '[]'
    assert repair_json("'\"'") == '"\\\""'
    assert repair_json("'string\"") == '"string\\\""'
    assert repair_json('{foo: [}') == '{"foo": []}'
    assert repair_json('{"key": "value:value"}') == '{"key": "value:value"}'
    assert repair_json('{“slanted_delimiter”: "value"}') == '{"slanted_delimiter": "value"}'
    assert (
        repair_json('{"name": "John", "age": 30, "city": "New')
        == '{"name": "John", "age": 30, "city": "New"}'
    )
    assert (
        repair_json('{"employees":["John", "Anna", "Peter')
        == '{"employees": ["John", "Anna", "Peter"]}'
    )
    assert (
        repair_json('{"employees":["John", "Anna", "Peter"]}')
        == '{"employees": ["John", "Anna", "Peter"]}'
    )
    assert (
        repair_json('{"text": "The quick brown fox,"}')
        == '{"text": "The quick brown fox,"}'
    )
    assert (
        repair_json('{"text": "The quick brown fox won\'t jump"}')
        == '{"text": "The quick brown fox won\'t jump"}'
    )
    assert {
        repair_json('{"value_1": "value_2": "data"}') == '{"value_1": "value_2", "data": ""}'
    }
    assert {
        repair_json('{"value_1": true, COMMENT "value_2": "data"}') == '{"value_1": "value_2", "": "data"}'
    }
    # Test with garbage comments
    assert repair_json('{"value_1": true, SHOULD_NOT_EXIST "value_2": "data" AAAA }') == '{"value_1": true, "value_2": "data"}'
    assert {
        repair_json('{"" : true, "key2": "value2"}') == '{" ": true, "key2": "value_2"}'
    }
    assert {
        repair_json('{"": true, "key2": "value2"}') == '{"empty_placeholder": true, "key2": "value_2"}'
    }
    # Test a nasty corner case
    assert repair_json(' - { "test_key": ["test_value", "test_value2"] }') == '{"test_key": ["test_value", "test_value2"]}'

    #Test markdown stupidities from ChatGPT
    assert repair_json('{ "content": "[LINK]("https://google.com")" }') == '{"content": "[LINK](\\"https://google.com\\")"}'
    assert repair_json('{ "content": "[LINK](" }') == '{"content": "[LINK]("}'
    assert repair_json('{ "content": "[LINK](", "key": true }') == '{"content": "[LINK](", "key": true}'
    assert repair_json("""
                       ```json
                       { "key": "value" }
                       ```""") == '{"key": "value"}'
    assert repair_json('````{ "key": "value" }```') == '{"key": "value"}'
    assert repair_json(r'{"real_content": "Some string: Some other string Some string <a href=\"https://domain.com\">Some link</a>"') == r'{"real_content": "Some string: Some other string Some string <a href=\\\"https://domain.com\\\">Some link</a>"}'
    assert repair_json('{"key\_1\n": "value"}') == '{"key_1": "value"}'
    assert repair_json('{"key\t\_": "value"}') == '{"key\\t_": "value"}'
    assert repair_json('{""answer"":[{""traits"":''Female aged 60+'',""answer1"":""5""}]}') == '{"answer": [{"traits": "Female aged 60+", "answer1": "5"}]}'
    assert repair_json('{"key":""') == '{"key": ""}'
    assert repair_json('{ "words": abcdef", "numbers": 12345", "words2": ghijkl" }') == '{"words": "abcdef", "numbers": 12345, "words2": "ghijkl"}'
    assert repair_json('{"key": 1/3}') == '{"key": "1/3"}'
    assert repair_json('{"key": .25}') == '{"key": 0.25}'
    assert repair_json("""{    "a": "",    "b": [ { "c": 1} ] \n}```""") == '{"a": "", "b": [{"c": 1}]}'


def test_repair_json_with_objects():
    # Test with valid JSON strings
    assert repair_json("[]", True) == []
    assert repair_json("{}", True) == {}
    assert repair_json('{"key": true, "key2": false, "key3": null}', True) == {"key": True, "key2": False, "key3": None}
    assert repair_json('{"name": "John", "age": 30, "city": "New York"}', True) == {
        "name": "John",
        "age": 30,
        "city": "New York",
    }
    assert repair_json("[1, 2, 3, 4]", True) == [1, 2, 3, 4]
    assert repair_json('{"employees":["John", "Anna", "Peter"]} ', True) == {
        "employees": ["John", "Anna", "Peter"]
    }

    # Test with invalid JSON strings
    assert repair_json('{"name": "John", "age": 30, "city": "New York', True) == {
        "name": "John",
        "age": 30,
        "city": "New York",
    }
    assert repair_json('{"name": "John", "age": 30, city: "New York"}', True) == {
        "name": "John",
        "age": 30,
        "city": "New York",
    }
    assert repair_json('{"name": "John", "age": 30, "city": New York}', True) == {
        "name": "John",
        "age": 30,
        "city": "New York",
    }
    assert repair_json("[1, 2, 3,", True) == [1, 2, 3]
    assert repair_json('{"employees":["John", "Anna",', True) == {
        "employees": ["John", "Anna"]
    }

    # Test with edge cases
    assert repair_json(" ", True) == ""
    assert repair_json("[", True) == []
    assert repair_json("{", True) == {}
    assert repair_json('{"key": "value:value"}', True) == {"key": "value:value"}
    assert repair_json("{'key': 'string', 'key2': false, \"key3\": null, \"key4\": unquoted}", True) == {"key": "string", "key2": False, "key3": None, "key4": "unquoted"}
    assert repair_json('{"name": "John", "age": 30, "city": "New', True) == {
        "name": "John",
        "age": 30,
        "city": "New",
    }
    assert repair_json('{"employees":["John", "Anna", "Peter', True) == {
        "employees": ["John", "Anna", "Peter"]
    }
    
    #Test with garbage comments
    assert repair_json('{"value_1": true, SHOULD_NOT_EXIST "value_2": "data" AAAA }', True) == {'value_1': True, 'value_2': 'data'}

    #Test markdown stupidities from ChatGPT
    assert repair_json('{ "content": "[LINK]("https://google.com")" }', True) == { "content": "[LINK](\"https://google.com\")"}
    assert repair_json('''
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
''', True) == {"resourceType": "Bundle", "id": "1", "type": "collection", "entry": [{"resource": {"resourceType": "Patient", "id": "1", "name": [{"use": "official", "family": "Corwin", "given": ["Keisha", "Sunny"], "prefix": ["Mrs."]}, {"use": "maiden", "family": "Goodwin", "given": ["Keisha", "Sunny"], "prefix": ["Mrs."]}]}}]}
    assert repair_json('{\n"html": "<h3 id="aaa">Waarom meer dan 200 Technical Experts - "Passie voor techniek"?</h3>"}', True) == {'html': '<h3 id="aaa">Waarom meer dan 200 Technical Experts - "Passie voor techniek"?</h3>'}


def test_repair_json_corner_cases_generate_by_gpt():
    # Test with nested JSON
    assert (
        repair_json('{"key1": {"key2": [1, 2, 3]}}') == '{"key1": {"key2": [1, 2, 3]}}'
    )
    assert repair_json('{"key1": {"key2": [1, 2, 3') == '{"key1": {"key2": [1, 2, 3]}}'

    # Test with empty keys
    assert repair_json('{"": "value"}') == '{"": "value"}'

    # Test with Unicode characters
    assert repair_json('{"key": "value\u263A"}') == '{"key": "value\\u263a"}'

    # Test with special characters
    assert repair_json('{"key": "value\\nvalue"}') == '{"key": "value\\nvalue"}'

    # Test with large numbers
    assert (
        repair_json('{"key": 12345678901234567890}') == '{"key": 12345678901234567890}'
    )

    # Test with whitespace
    assert repair_json(' { "key" : "value" } ') == '{"key": "value"}'

    # Test with null values
    assert repair_json('{"key": null}') == '{"key": null}'

    # Test with numeric-like values
    assert repair_json('{"key": 10-20}') == '{"key": "10-20"}'
    assert repair_json('{"key": 1.1.1}') == '{"key": "1.1.1"}'


def test_repair_json_corner_cases_generate_by_gpt_with_objects():
    # Test with nested JSON
    assert repair_json('{"key1": {"key2": [1, 2, 3]}}', True) == {
        "key1": {"key2": [1, 2, 3]}
    }
    assert repair_json('{"key1": {"key2": [1, 2, 3', True) == {
        "key1": {"key2": [1, 2, 3]}
    }

    # Test with empty keys
    assert repair_json('{"": "value"}', True) == {"": "value"}

    # Test with Unicode characters
    assert repair_json('{"key": "value\u263A"}', True) == {"key": "value☺"}

    # Test with special characters
    assert repair_json('{"key": "value\\nvalue"}', True) == {"key": "value\nvalue"}

    # Test with large numbers
    assert repair_json('{"key": 12345678901234567890}', True) == {
        "key": 12345678901234567890
    }

    # Test with whitespace
    assert repair_json(' { "key" : "value" } ', True) == {"key": "value"}

    # Test with null values
    assert repair_json('{"key": null}', True) == {"key": None}

    # Test with numeric-like values
    assert repair_json('{"key": 10-20}', True) == {"key": "10-20"}
    assert repair_json('{"key": 1.1.1}', True) == {"key": "1.1.1"}


def test_repair_json_skip_json_loads():
    assert repair_json('{"key": true, "key2": false, "key3": null}', skip_json_loads=True) == '{"key": true, "key2": false, "key3": null}'
    assert repair_json('{"key": true, "key2": false, "key3": null}', return_objects=True, skip_json_loads=True) == {"key": True, "key2": False, "key3": None}
    assert repair_json('{"key": true, "key2": false, "key3": }', skip_json_loads=True) == '{"key": true, "key2": false, "key3": ""}'
    assert loads('{"key": true, "key2": false, "key3": }', skip_json_loads=True) == {"key": True, "key2": False, "key3": ""}


def test_repair_json_from_file():
    import os
    import tempfile

    # Create a temporary file
    temp_fd, temp_path = tempfile.mkstemp(suffix=".json")
    try:
        # Write content to the temporary file
        with os.fdopen(temp_fd, 'w') as tmp:
            tmp.write("{")
        
        assert(from_file(temp_path, logging=True)) == ({},[])
        
    finally:
        # Clean up - delete the temporary file
        os.remove(temp_path)

   
    assert repair_json('{"key": 1/3, "foo": "bar"}') == '{"key": "1/3", "foo": "bar"}'
    assert repair_json('{"here": "now", "key": 1/3, "foo": "bar"}') == '{"here": "now", "key": "1/3", "foo": "bar"}'
    assert repair_json('{"key": 12345/67890}') == '{"key": "12345/67890"}'
