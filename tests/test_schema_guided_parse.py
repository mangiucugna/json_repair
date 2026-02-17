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


def test_schema_applies_to_valid_json_without_skip_json_loads():
    pytest.importorskip("jsonschema")
    schema = {
        "type": "object",
        "properties": {"value": {"type": "integer"}},
        "required": ["value"],
    }
    # Fast-path validation fails, then parser+schema fallback repairs.
    assert repair_json('{"value": "1"}', schema=schema, return_objects=True) == {"value": 1}
    # Fast-path validation fails for a valid scalar and parser fallback returns empty string.
    assert repair_json("true", schema={"type": "string"}, return_objects=True) == ""

    with pytest.raises(ValueError, match="does not match"):
        repair_json('"bbb"', schema={"type": "string", "pattern": "^a+$"}, return_objects=True)


def test_schema_valid_fast_path_keeps_logging_empty():
    pytest.importorskip("jsonschema")
    schema = {
        "type": "object",
        "properties": {"value": {"type": "integer"}},
        "required": ["value"],
    }
    repaired, logs = repair_json('{"value": 1}', schema=schema, logging=True)
    assert repaired == {"value": 1}
    assert logs == []


def test_schema_applies_to_valid_json_fast_path_outputs_and_logging():
    pytest.importorskip("jsonschema")
    schema = {
        "type": "object",
        "properties": {"value": {"type": "integer"}},
        "required": ["value"],
    }
    assert repair_json('{"value": "1"}', schema=schema) == '{"value": 1}'

    repaired, logs = repair_json('{"value": "1"}', schema=schema, logging=True)
    assert repaired == {"value": 1}
    assert logs


def test_schema_applies_to_valid_empty_string():
    pytest.importorskip("jsonschema")
    assert repair_json('""', schema={"type": "string"}) == ""


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


def test_schema_boolean_coercion_is_mode_independent():
    pytest.importorskip("jsonschema")
    schema = {
        "type": "object",
        "properties": {"flag": {"type": "boolean"}},
        "required": ["flag"],
    }

    raw = '{"flag": "yes"}'
    default_mode = repair_json(raw, schema=schema, skip_json_loads=True, return_objects=True)
    standard_mode = repair_json(
        raw,
        schema=schema,
        skip_json_loads=True,
        return_objects=True,
        schema_repair_mode="standard",
    )
    salvage_mode = repair_json(
        raw,
        schema=schema,
        skip_json_loads=True,
        return_objects=True,
        schema_repair_mode="salvage",
    )
    assert default_mode == {"flag": True}
    assert standard_mode == {"flag": True}
    assert salvage_mode == {"flag": True}


def test_schema_boolean_coercion_accepts_number_tokens():
    pytest.importorskip("jsonschema")
    schema = {
        "type": "object",
        "properties": {"flag": {"type": "boolean"}},
        "required": ["flag"],
    }
    assert repair_with_schema('{"flag": 1}', schema) == {"flag": True}
    assert repair_with_schema('{"flag": 0}', schema) == {"flag": False}
    assert repair_with_schema('{"flag": 1.0}', schema) == {"flag": True}
    assert repair_with_schema('{"flag": 0.0}', schema) == {"flag": False}


def test_schema_salvage_mode_drops_invalid_array_items():
    pytest.importorskip("jsonschema")
    schema = {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "score": {"type": "number"},
                    },
                    "required": ["id", "score"],
                },
            }
        },
        "required": ["items"],
    }
    raw = '{"items":[{"id":1,"score":85.6},{"id":2,"score":"N/A"}]}'

    with pytest.raises(ValueError, match="Expected number"):
        repair_with_schema(raw, schema)

    repaired = repair_json(
        raw,
        schema=schema,
        skip_json_loads=True,
        return_objects=True,
        schema_repair_mode="salvage",
    )
    assert repaired == {"items": [{"id": 1, "score": 85.6}]}

    repaired_with_logs, logs = repair_json(
        raw,
        schema=schema,
        skip_json_loads=True,
        logging=True,
        schema_repair_mode="salvage",
    )
    assert repaired_with_logs == {"items": [{"id": 1, "score": 85.6}]}
    assert isinstance(logs, list)
    assert any(log["text"] == "Dropped invalid array item while salvaging" for log in logs)


def test_schema_salvage_mode_still_enforces_min_items():
    pytest.importorskip("jsonschema")
    schema = {
        "type": "array",
        "items": {"type": "integer"},
        "minItems": 2,
    }
    with pytest.raises(ValueError, match="minItems"):
        repair_json(
            '["1", "bad"]',
            schema=schema,
            skip_json_loads=True,
            return_objects=True,
            schema_repair_mode="salvage",
        )


def test_schema_salvage_mode_does_not_hide_schema_definition_errors():
    pytest.importorskip("jsonschema")
    schema = {"type": "array", "items": {"type": "bogus"}}
    with pytest.raises(ValueError, match="Unsupported schema type bogus"):
        repair_json(
            "[1]",
            schema=schema,
            skip_json_loads=True,
            return_objects=True,
            schema_repair_mode="salvage",
        )


def test_schema_salvage_mode_maps_list_to_object_when_unambiguous():
    pytest.importorskip("jsonschema")
    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "tags": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["name", "tags"],
    }
    raw = '["hello", ["a", "b"]]'

    with pytest.raises(ValueError, match="Expected object"):
        repair_json(raw, schema=schema, skip_json_loads=True, return_objects=True)

    assert repair_json(
        raw,
        schema=schema,
        skip_json_loads=True,
        return_objects=True,
        schema_repair_mode="salvage",
    ) == {"name": "hello", "tags": ["a", "b"]}


def test_schema_salvage_mode_mapping_rejects_length_mismatch():
    pytest.importorskip("jsonschema")
    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "tags": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["name", "tags"],
    }
    with pytest.raises(ValueError, match="Expected object"):
        repair_json(
            '["hello"]',
            schema=schema,
            skip_json_loads=True,
            return_objects=True,
            schema_repair_mode="salvage",
        )


def test_schema_salvage_mode_mapping_rejects_type_mismatch():
    pytest.importorskip("jsonschema")
    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "tags": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["name", "tags"],
    }
    with pytest.raises(ValueError, match="Expected object"):
        repair_json(
            '[["a", "b"], "hello"]',
            schema=schema,
            skip_json_loads=True,
            return_objects=True,
            schema_repair_mode="salvage",
        )


def test_schema_salvage_mode_requires_schema():
    with pytest.raises(ValueError, match="schema_repair_mode"):
        repair_json("{}", return_objects=True, schema_repair_mode="salvage")
