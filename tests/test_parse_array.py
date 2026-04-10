from src.json_repair.json_parser import JSONParser
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
    assert (
        repair_json(
            '{"headers": ["A", "B", "C"], "rows": [["r1a", "r1b", "r1c"], ["r2a", "r2b", "r2c"], '
            '"r3a", "r3b", "r3c"], ["r4a", "r4b", "r4c"], ["r5a", "r5b", "r5c"]]}'
        )
        == '{"headers": ["A", "B", "C"], "rows": [["r1a", "r1b", "r1c"], ["r2a", "r2b", "r2c"], '
        '["r3a", "r3b", "r3c"], ["r4a", "r4b", "r4c"], ["r5a", "r5b", "r5c"]]}'
    )
    assert repair_json('{"key": ["value" "value1" "value2"]}') == '{"key": ["value", "value1", "value2"]}'
    assert (
        repair_json('{"key": ["lorem "ipsum" dolor "sit" amet, "consectetur" ", "lorem "ipsum" dolor", "lorem"]}')
        == '{"key": ["lorem \\"ipsum\\" dolor \\"sit\\" amet, \\"consectetur\\" ", "lorem \\"ipsum\\" dolor", "lorem"]}'
    )
    assert repair_json('{"k"e"y": "value"}') == '{"k\\"e\\"y": "value"}'
    assert repair_json('["key":"value"}]') == '[{"key": "value"}]'
    assert repair_json('["key":"value"]') == '[{"key": "value"}]'
    assert repair_json('[ "key":"value"]') == '[{"key": "value"}]'
    assert repair_json('[{"key": "value", "key') == '[{"key": "value"}, ["key"]]'
    assert repair_json("{'key1', 'key2'}") == '["key1", "key2"]'


def test_parse_array_python_tuple_literals():
    assert repair_json('("a", "b", "c")', return_objects=True) == ["a", "b", "c"]
    assert repair_json("((1, 2), (3, 4))", return_objects=True) == [[1, 2], [3, 4]]
    assert repair_json('{"coords": (1, 2), "ok": true}', return_objects=True) == {"coords": [1, 2], "ok": True}
    assert repair_json('{"empty": ()}', return_objects=True) == {"empty": []}


def test_parse_array_parenthesized_scalar_keeps_scalar_shape():
    assert repair_json("(1)", return_objects=True) == 1
    assert repair_json('("x")', return_objects=True) == "x"
    assert repair_json('{"scalar_group": (1)}', return_objects=True) == {"scalar_group": 1}
    assert repair_json('{"string_group": ("x")}', return_objects=True) == {"string_group": "x"}


def test_parse_array_mismatched_parenthesis_still_logs_missing_bracket():
    repaired, logs = repair_json("[1, 2)", return_objects=True, logging=True)

    assert repaired == [1, 2]
    assert any("closing ]" in entry["text"] for entry in logs)


def test_parenthesized_tuple_classifier_handles_nested_delimiters_and_missing_close():
    parser = JSONParser('({"text": "a\\\\b", "items": [1]})', None, False)
    assert parser.parenthesized_is_explicit_tuple() is False

    parser = JSONParser("(1", None, False)
    assert parser.parenthesized_is_explicit_tuple() is False


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
