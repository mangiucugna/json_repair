import pytest

from src.json_repair import repair_json


def repair_with_schema(raw, schema, **kwargs):
    return repair_json(raw, schema=schema, skip_json_loads=True, return_objects=True, **kwargs)


def test_schema_guides_missing_value_type_defaults():
    pytest.importorskip("jsonschema")
    schema = {
        "type": "object",
        "properties": {
            "text": {"type": "string"},
            "count": {"type": "integer"},
            "ratio": {"type": "number"},
            "flag": {"type": "boolean"},
            "items": {"type": "array", "items": {"type": "string"}},
            "payload": {"type": "object"},
            "nothing": {"type": "null"},
        },
        "required": ["text", "count", "ratio", "flag", "items", "payload", "nothing"],
    }
    raw = '{ "text": , "count": , "ratio": , "flag": , "items": , "payload": , "nothing": }'
    assert repair_with_schema(raw, schema) == {
        "text": "",
        "count": 0,
        "ratio": 0,
        "flag": False,
        "items": [],
        "payload": {},
        "nothing": None,
    }


def test_schema_missing_required_property_raises():
    pytest.importorskip("jsonschema")
    schema = {
        "type": "object",
        "properties": {"required_value": {"type": "integer", "default": 1}},
        "required": ["required_value"],
    }
    with pytest.raises(ValueError, match="Missing required properties"):
        repair_with_schema("{}", schema)


def test_schema_optional_default_is_inserted():
    pytest.importorskip("jsonschema")
    schema = {
        "type": "object",
        "properties": {"note": {"type": "string", "default": "n/a"}},
    }
    assert repair_with_schema("{}", schema) == {"note": "n/a"}


def test_schema_and_strict_are_mutually_exclusive():
    with pytest.raises(ValueError, match="schema and strict"):
        repair_json("{}", schema={}, strict=True, return_objects=True)


def test_schema_pydantic_v2_defaults():
    pydantic = pytest.importorskip("pydantic")
    version = getattr(pydantic, "VERSION", getattr(pydantic, "__version__", "0"))
    if int(version.split(".")[0]) < 2:
        pytest.skip("pydantic v2 required")

    base_model = pydantic.BaseModel
    field = pydantic.Field

    class SchemaModel(base_model):
        evidence_types: list[str] = field(default_factory=list)

    raw = '{ "evidence_types": }'
    assert repair_with_schema(raw, SchemaModel) == {"evidence_types": []}
