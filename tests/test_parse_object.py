from src.json_repair.json_repair import repair_json


def test_parse_object():
    assert repair_json("{}", return_objects=True) == {}
    assert repair_json('{ "key": "value", "key2": 1, "key3": True }', return_objects=True) == {
        "key": "value",
        "key2": 1,
        "key3": True,
    }
    assert repair_json("{", return_objects=True) == {}
    assert repair_json('{ "key": value, "key2": 1 "key3": null }', return_objects=True) == {
        "key": "value",
        "key2": 1,
        "key3": None,
    }
    assert repair_json("   {  }   ") == "{}"
    assert repair_json("{") == "{}"
    assert repair_json("}") == ""
    assert repair_json('{"') == "{}"


def test_parse_object_edge_cases():
    assert repair_json("{foo: [}") == '{"foo": []}'
    assert repair_json('{"": "value"') == '{"": "value"}'
    assert repair_json('{"key": "v"alue"}') == '{"key": "v\\"alue\\""}'
    assert repair_json('{"value_1": true, COMMENT "value_2": "data"}') == '{"value_1": true, "value_2": "data"}'
    assert (
        repair_json('{"value_1": true, SHOULD_NOT_EXIST "value_2": "data" AAAA }')
        == '{"value_1": true, "value_2": "data"}'
    )
    assert repair_json('{"" : true, "key2": "value2"}') == '{"": true, "key2": "value2"}'
    assert (
        repair_json("""{""answer"":[{""traits"":''Female aged 60+'',""answer1"":""5""}]}""")
        == '{"answer": [{"traits": "Female aged 60+", "answer1": "5"}]}'
    )
    assert (
        repair_json('{ "words": abcdef", "numbers": 12345", "words2": ghijkl" }')
        == '{"words": "abcdef", "numbers": 12345, "words2": "ghijkl"}'
    )
    assert (
        repair_json("""{"number": 1,"reason": "According...""ans": "YES"}""")
        == '{"number": 1, "reason": "According...", "ans": "YES"}'
    )
    assert repair_json("""{ "a" : "{ b": {} }" }""") == '{"a": "{ b"}'
    assert repair_json("""{"b": "xxxxx" true}""") == '{"b": "xxxxx"}'
    assert repair_json('{"key": "Lorem "ipsum" s,"}') == '{"key": "Lorem \\"ipsum\\" s,"}'
    assert repair_json('{"lorem": ipsum, sic, datum.",}') == '{"lorem": "ipsum, sic, datum."}'
    assert (
        repair_json('{"lorem": sic tamet. "ipsum": sic tamet, quick brown fox. "sic": ipsum}')
        == '{"lorem": "sic tamet.", "ipsum": "sic tamet", "sic": "ipsum"}'
    )
    assert (
        repair_json('{"lorem_ipsum": "sic tamet, quick brown fox. }')
        == '{"lorem_ipsum": "sic tamet, quick brown fox."}'
    )
    assert repair_json('{"key":value, " key2":"value2" }') == '{"key": "value", " key2": "value2"}'
    assert repair_json('{"key":value "key2":"value2" }') == '{"key": "value", "key2": "value2"}'
    assert (
        repair_json("{'text': 'words{words in brackets}more words'}")
        == '{"text": "words{words in brackets}more words"}'
    )
    assert repair_json("{text:words{words in brackets}}") == '{"text": "words{words in brackets}"}'
    assert repair_json("{text:words{words in brackets}m}") == '{"text": "words{words in brackets}m"}'
    assert repair_json('{"key": "value, value2"```') == '{"key": "value, value2"}'
    assert repair_json('{"key": "value}```') == '{"key": "value"}'
    assert repair_json("{key:value,key2:value2}") == '{"key": "value", "key2": "value2"}'
    assert repair_json('{"key:"value"}') == '{"key": "value"}'
    assert repair_json('{"key:value}') == '{"key": "value"}'
    assert (
        repair_json('[{"lorem": {"ipsum": "sic"}, """" "lorem": {"ipsum": "sic"}]')
        == '[{"lorem": {"ipsum": "sic"}}, {"lorem": {"ipsum": "sic"}}]'
    )
    assert (
        repair_json('{ "key": ["arrayvalue"], ["arrayvalue1"], ["arrayvalue2"], "key3": "value3" }')
        == '{"key": ["arrayvalue", "arrayvalue1", "arrayvalue2"], "key3": "value3"}'
    )
    assert (
        repair_json('{ "key": ["arrayvalue"], "key3": "value3", ["arrayvalue1"] }')
        == '{"key": ["arrayvalue"], "key3": "value3", "arrayvalue1": ""}'
    )
    assert (
        repair_json('{"key": "{\\\\"key\\\\\\":[\\"value\\\\\\"],\\"key2\\":"value2"}"}')
        == '{"key": "{\\"key\\":[\\"value\\"],\\"key2\\":\\"value2\\"}"}'
    )
    assert repair_json('{"key": , "key2": "value2"}') == '{"key": "", "key2": "value2"}'


def test_parse_object_merge_at_the_end():
    assert repair_json('{"key": "value"}, "key2": "value2"}') == '{"key": "value", "key2": "value2"}'
    assert repair_json('{"key": "value"}, "key2": }') == '{"key": "value", "key2": ""}'
    assert repair_json('{"key": "value"}, []') == '[{"key": "value"}, []]'
    assert repair_json('{"key": "value"}, ["abc"]') == '[{"key": "value"}, ["abc"]]'
    assert repair_json('{"key": "value"}, {}') == '[{"key": "value"}, {}]'
    assert repair_json('{"key": "value"}, "" : "value2"}') == '{"key": "value", "": "value2"}'
    assert repair_json('{"key": "value"}, "key2" "value2"}') == '{"key": "value", "key2": "value2"}'
    assert (
        repair_json('{"key1": "value1"}, "key2": "value2", "key3": "value3"}')
        == '{"key1": "value1", "key2": "value2", "key3": "value3"}'
    )
