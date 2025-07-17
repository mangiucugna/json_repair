from src.json_repair.json_repair import repair_json


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
