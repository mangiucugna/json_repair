from src.json_repair.json_repair import repair_json


def test_parse_array():
    assert repair_json("[]", return_objects=True) == []
    assert repair_json("[1, 2, 3, 4]", return_objects=True) == [1, 2, 3, 4]
    assert repair_json("[", return_objects=True) == []
    assert repair_json("[[1\n\n]") == "[[1]]"


def test_parse_array_edge_cases():
    assert repair_json("[{]") == "[]"
    assert repair_json("[") == "[]"
    assert repair_json('["') == "[]"
    assert repair_json("]") == ""
    assert repair_json("[1, 2, 3,") == "[1, 2, 3]"
    assert repair_json("[1, 2, 3, ...]") == "[1, 2, 3]"
    assert repair_json("[1, 2, ... , 3]") == "[1, 2, 3]"
    assert repair_json("[1, 2, '...', 3]") == '[1, 2, "...", 3]'
    assert repair_json("[true, false, null, ...]") == "[true, false, null]"
    assert repair_json('["a" "b" "c" 1') == '["a", "b", "c", 1]'
    assert repair_json('{"employees":["John", "Anna",') == '{"employees": ["John", "Anna"]}'
    assert repair_json('{"employees":["John", "Anna", "Peter') == '{"employees": ["John", "Anna", "Peter"]}'
    assert repair_json('{"key1": {"key2": [1, 2, 3') == '{"key1": {"key2": [1, 2, 3]}}'
    assert repair_json('{"key": ["value]}') == '{"key": ["value"]}'
    assert repair_json('["lorem "ipsum" sic"]') == '["lorem \\"ipsum\\" sic"]'
    assert (
        repair_json('{"key1": ["value1", "value2"}, "key2": ["value3", "value4"]}')
        == '{"key1": ["value1", "value2"], "key2": ["value3", "value4"]}'
    )
    assert repair_json('{"key": ["value" "value1" "value2"]}') == '{"key": ["value", "value1", "value2"]}'
    assert (
        repair_json('{"key": ["lorem "ipsum" dolor "sit" amet, "consectetur" ", "lorem "ipsum" dolor", "lorem"]}')
        == '{"key": ["lorem \\"ipsum\\" dolor \\"sit\\" amet, \\"consectetur\\" ", "lorem \\"ipsum\\" dolor", "lorem"]}'
    )
    assert repair_json('{"k"e"y": "value"}') == '{"k\\"e\\"y": "value"}'
    assert repair_json('["key":"value"}]') == '[{"key": "value"}]'
    assert repair_json('[{"key": "value", "key') == '[{"key": "value"}, ["key"]]'
    assert repair_json("{'key1', 'key2'}") == '["key1", "key2"]'


def test_parse_array_missing_quotes():
    assert repair_json('["value1" value2", "value3"]') == '["value1", "value2", "value3"]'
    assert (
        repair_json('{"bad_one":["Lorem Ipsum", "consectetur" comment" ], "good_one":[ "elit", "sed", "tempor"]}')
        == '{"bad_one": ["Lorem Ipsum", "consectetur", "comment"], "good_one": ["elit", "sed", "tempor"]}'
    )
    assert (
        repair_json('{"bad_one": ["Lorem Ipsum","consectetur" comment],"good_one": ["elit","sed","tempor"]}')
        == '{"bad_one": ["Lorem Ipsum", "consectetur", "comment"], "good_one": ["elit", "sed", "tempor"]}'
    )
