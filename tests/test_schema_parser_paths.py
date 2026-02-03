import pytest

from src.json_repair import repair_json
from src.json_repair.json_parser import JSONParser
from src.json_repair.schema_repair import SchemaRepairer
from src.json_repair.utils.json_context import ContextValues


def parse_object_direct(raw, schema, *, strict=False, context=None):
    parser = JSONParser(raw, None, False, 0, False, strict)
    repairer = SchemaRepairer(schema if isinstance(schema, dict) else {}, None)
    parser.schema_repairer = repairer
    if context is not None:
        parser.context.set(context)
    parser.index = 1
    return parser.parse_object(schema, "$")


def parse_array_direct(raw, schema):
    parser = JSONParser(raw, None, False, 0, False, False)
    repairer = SchemaRepairer(schema if isinstance(schema, dict) else {}, None)
    parser.schema_repairer = repairer
    parser.index = 1
    return parser.parse_array(schema, "$")


def test_parse_object_schema_true_false_and_non_object():
    assert parse_object_direct("{}", True) == {}
    with pytest.raises(ValueError, match="Schema does not allow"):
        parse_object_direct("{}", False)
    assert parse_object_direct("{}", {"type": "string"}) == {}


def test_parse_object_schema_property_fallbacks_and_stray_colon():
    schema = {
        "type": "object",
        "properties": [],
        "patternProperties": [],
        "additionalProperties": True,
    }
    assert parse_object_direct("{:a:1}", schema) == {"a": 1}


def test_parse_object_schema_invalid_property_schema_raises():
    schema = {"type": "object", "properties": {"a": "nope"}}
    with pytest.raises(ValueError, match="Schema must be an object"):
        parse_object_direct('{"a": 1}', schema)


def test_parse_object_schema_invalid_pattern_schema_raises():
    schema = {"type": "object", "patternProperties": {"^a": "nope"}}
    with pytest.raises(ValueError, match="Schema must be an object"):
        parse_object_direct('{"a": 1}', schema)


def test_parse_object_schema_invalid_pattern_extra_schema_raises():
    schema = {
        "type": "object",
        "patternProperties": {"^a": {"type": "integer"}, "a$": "nope"},
    }
    with pytest.raises(ValueError, match="Schema must be an object"):
        parse_object_direct('{"a": 1}', schema)


def test_parse_array_schema_missing_object_brace():
    schema = {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {"a": {"type": "integer"}},
            "required": ["a"],
        },
    }
    assert repair_json('["a": 1]', schema=schema, skip_json_loads=True, return_objects=True) == [{"a": 1}]


def test_parse_object_schema_pattern_extra_schemas():
    schema = {
        "type": "object",
        "patternProperties": {
            "^x": {"type": "integer"},
            "1$": {"type": "integer"},
        },
    }
    assert repair_json('{"x1": "2"}', schema=schema, skip_json_loads=True, return_objects=True) == {"x1": 2}


def test_parse_object_schema_drop_property_and_additional_schema():
    schema_drop = {
        "type": "object",
        "properties": {"a": {"type": "integer"}},
        "additionalProperties": False,
    }
    assert repair_json('{"a": 1, "extra": "drop"}', schema=schema_drop, skip_json_loads=True, return_objects=True) == {
        "a": 1
    }

    schema_extra = {
        "type": "object",
        "additionalProperties": {"type": "integer"},
    }
    assert repair_json('{"a": "2"}', schema=schema_extra, skip_json_loads=True, return_objects=True) == {"a": 2}


def test_parse_object_schema_closing_array_bracket_and_extra_brace():
    schema = {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {"a": {"type": "integer"}},
            "required": ["a"],
        },
    }
    assert repair_json('[{"a": 1]', schema=schema, skip_json_loads=True, return_objects=True) == [{"a": 1}]

    schema_obj = {"type": "object", "additionalProperties": True}
    parser = JSONParser('{"a": 1}}', None, False, 0, False, False)
    repairer = SchemaRepairer(schema_obj, None)
    parser.schema_repairer = repairer
    parser.context.set(ContextValues.ARRAY)
    parser.index = 1
    assert parser.parse_object(schema_obj, "$") == {"a": 1}


def test_parse_object_schema_empty_object_falls_back_to_array():
    schema = {"type": "object", "additionalProperties": True}
    assert parse_object_direct("{,,}", schema) == []


def test_parse_array_schema_true_false_and_non_array():
    assert parse_array_direct("[1]", True) == [1]
    with pytest.raises(ValueError, match="Schema does not allow"):
        parse_array_direct("[1]", False)
    assert parse_array_direct("[1]", {"type": "object"}) == [1]


def test_parse_array_schema_items_and_additional_items():
    schema_drop = {"type": "array", "items": [{"type": "integer"}], "additionalItems": False}
    assert parse_array_direct("[1, 2]", schema_drop) == [1]

    schema_extra = {
        "type": "array",
        "items": [{"type": "integer"}],
        "additionalItems": {"type": "integer"},
    }
    assert parse_array_direct('[1, "2"]', schema_extra) == [1, 2]

    schema_open = {
        "type": "array",
        "items": [{"type": "integer"}],
        "additionalItems": True,
    }
    assert parse_array_direct('[1, "x"]', schema_open) == [1, "x"]

    schema_items = {"type": "array", "items": {"type": "integer"}}
    assert parse_array_direct('["1"]', schema_items) == [1]

    schema_any = {"type": "array"}
    assert parse_array_direct("[true]", schema_any) == [True]


def test_parse_array_schema_invalid_items_schema_raises():
    schema = {"type": "array", "items": ["nope"]}
    with pytest.raises(ValueError, match="Schema must be an object"):
        parse_array_direct("[1]", schema)


def test_parse_json_with_schema_branches():
    schema = {"type": "array", "items": {"type": "integer"}}
    parser = JSONParser("[1]", None, False, 0, False, False)
    repairer = SchemaRepairer(schema, None)
    parser.schema_repairer = repairer
    assert parser.parse_json(schema, "$") == [1]

    parser = JSONParser('"1"', None, False, 0, False, False)
    parser.schema_repairer = repairer
    parser.context.set(ContextValues.ARRAY)
    assert parser.parse_json({"type": "integer"}, "$") == 1

    parser = JSONParser("1", None, False, 0, False, False)
    parser.schema_repairer = repairer
    parser.context.set(ContextValues.ARRAY)
    assert parser.parse_json({"type": "integer"}, "$") == 1

    parser = JSONParser("# comment", None, False, 0, False, False)
    parser.schema_repairer = repairer
    assert parser.parse_json({"type": "string"}, "$") == ""

    parser = JSONParser("", None, False, 0, False, False)
    parser.schema_repairer = repairer
    assert parser.parse_json({"type": "string"}, "$") == ""

    parser = JSONParser('"x"', None, False, 0, False, False)
    parser.schema_repairer = repairer
    parser.context.set(ContextValues.ARRAY)
    assert parser.parse_json(True, "$") == "x"
    with pytest.raises(ValueError, match="Schema does not allow"):
        parser.parse_json(False, "$")

    parser = JSONParser('@{"a": 1}', None, False, 0, False, False)
    parser.schema_repairer = SchemaRepairer({"type": "object"}, None)
    assert parser.parse_json({"type": "object"}, "$") == {"a": 1}


def test_schema_ref_to_true_short_circuits():
    schema = {"flag": True}
    repairer = SchemaRepairer(schema, None)

    parser = JSONParser("[1]", None, False, 0, False, False)
    parser.schema_repairer = repairer
    parser.index = 1
    assert parser.parse_array({"$ref": "#/flag"}, "$") == [1]

    parser = JSONParser('{"a": 1}', None, False, 0, False, False)
    parser.schema_repairer = repairer
    parser.index = 1
    assert parser.parse_object({"$ref": "#/flag"}, "$") == {"a": 1}

    parser = JSONParser("1", None, False, 0, False, False)
    parser.schema_repairer = repairer
    parser.context.set(ContextValues.ARRAY)
    assert parser.parse_json({"$ref": "#/flag"}, "$") == 1
