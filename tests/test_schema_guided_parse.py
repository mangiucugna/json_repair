from typing import cast

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
    # Fast-path validation fails for a scalar, but schema-aware repair can fix it directly.
    assert repair_json('"1"', schema={"type": "integer"}, return_objects=True) == 1
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


def test_schema_skip_json_loads_keeps_parser_path_for_scalars():
    pytest.importorskip("jsonschema")
    assert repair_json("True", schema={"type": "string"}, skip_json_loads=True, return_objects=True) == ""
    with pytest.raises(ValueError, match="is not of type"):
        repair_json('"1"', schema={"type": "integer"}, skip_json_loads=True, return_objects=True)


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


def test_schema_pydantic_model_keeps_literal_fenced_snippet_in_multiline_string():
    pytest.importorskip("jsonschema")
    pydantic = pytest.importorskip("pydantic")
    version = getattr(pydantic, "VERSION", getattr(pydantic, "__version__", "0"))
    if int(version.split(".")[0]) < 2:
        pytest.skip("pydantic v2 required")

    class SchemaModel(pydantic.BaseModel):
        a: str
        b: str

    raw = '{\n"a": "\n```{}```\n",\n"b": "x",\n}'
    expected = {"a": "\n```{}```", "b": "x"}
    schema = SchemaModel.model_json_schema()

    assert repair_json(raw, schema=schema, return_objects=True) == expected
    assert repair_json(raw, schema=schema, skip_json_loads=True, return_objects=True) == expected


def test_schema_pydantic_model_keeps_literal_fenced_snippet_before_stray_quote_line():
    pytest.importorskip("jsonschema")
    pydantic = pytest.importorskip("pydantic")
    version = getattr(pydantic, "VERSION", getattr(pydantic, "__version__", "0"))
    if int(version.split(".")[0]) < 2:
        pytest.skip("pydantic v2 required")

    class SchemaModel(pydantic.BaseModel):
        a: str
        b: str

    raw = '{\n"a": "\n```{}```\n"\n",\n"b": "x",\n}'
    expected = {"a": '\n```{}```\n"', "b": "x"}
    schema = SchemaModel.model_json_schema()

    assert repair_json(raw, schema=schema, return_objects=True) == expected
    assert repair_json(raw, schema=schema, skip_json_loads=True, return_objects=True) == expected


def test_schema_pydantic_model_keeps_literal_fenced_snippet_before_stray_quote_line_with_single_quoted_key():
    pytest.importorskip("jsonschema")
    pydantic = pytest.importorskip("pydantic")
    version = getattr(pydantic, "VERSION", getattr(pydantic, "__version__", "0"))
    if int(version.split(".")[0]) < 2:
        pytest.skip("pydantic v2 required")

    class SchemaModel(pydantic.BaseModel):
        a: str
        b: str

    raw = '{\n"a": "\n```{}```\n"\n",\n\'b\': "x",\n}'
    expected = {"a": '\n```{}```\n"', "b": "x"}
    schema = SchemaModel.model_json_schema()

    assert repair_json(raw, schema=schema, return_objects=True) == expected
    assert repair_json(raw, schema=schema, skip_json_loads=True, return_objects=True) == expected


def test_schema_pydantic_model_keeps_literal_fenced_snippet_before_stray_quote_line_with_comment_before_key():
    pytest.importorskip("jsonschema")
    pydantic = pytest.importorskip("pydantic")
    version = getattr(pydantic, "VERSION", getattr(pydantic, "__version__", "0"))
    if int(version.split(".")[0]) < 2:
        pytest.skip("pydantic v2 required")

    class SchemaModel(pydantic.BaseModel):
        a: str
        b: str

    raw = '{\n"a": "\n```{}```\n"\n", // c\n"b": "x",\n}'
    expected = {"a": '\n```{}```\n"', "b": "x"}
    schema = SchemaModel.model_json_schema()

    assert repair_json(raw, schema=schema, return_objects=True) == expected
    assert repair_json(raw, schema=schema, skip_json_loads=True, return_objects=True) == expected


def test_schema_pydantic_model_keeps_literal_fenced_snippet_before_stray_quote_line_with_bare_key():
    pytest.importorskip("jsonschema")
    pydantic = pytest.importorskip("pydantic")
    version = getattr(pydantic, "VERSION", getattr(pydantic, "__version__", "0"))
    if int(version.split(".")[0]) < 2:
        pytest.skip("pydantic v2 required")

    class SchemaModel(pydantic.BaseModel):
        a: str
        b: str

    raw = '{\n"a": "\n```{}```\n"\n",\n b: "x",\n}'
    expected = {"a": '\n```{}```\n"', "b": "x"}
    schema = SchemaModel.model_json_schema()

    assert repair_json(raw, schema=schema, return_objects=True) == expected
    assert repair_json(raw, schema=schema, skip_json_loads=True, return_objects=True) == expected


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


def test_schema_salvage_mode_maps_set_like_object_members_to_null_valued_keys():
    pytest.importorskip("jsonschema")
    schema = {"type": "object"}
    raw = '{"a", "b"}'

    with pytest.raises(ValueError, match="Expected object"):
        repair_json(raw, schema=schema, skip_json_loads=True, return_objects=True, schema_repair_mode="standard")

    assert repair_json(
        raw,
        schema=schema,
        skip_json_loads=True,
        return_objects=True,
        schema_repair_mode="salvage",
    ) == {"a": None, "b": None}
    assert (
        repair_json(
            raw,
            schema=schema,
            skip_json_loads=True,
            schema_repair_mode="salvage",
        )
        == '{"a": null, "b": null}'
    )

    repaired_with_logs, logs = cast(
        "tuple[object, list[dict[str, str]]]",
        repair_json(
            raw,
            schema=schema,
            skip_json_loads=True,
            logging=True,
            schema_repair_mode="salvage",
        ),
    )
    assert repaired_with_logs == {"a": None, "b": None}
    assert any("set-like members as null-valued object keys" in log["text"] for log in logs)


def test_schema_salvage_mode_set_like_members_do_not_override_mixed_object_array_schema():
    pytest.importorskip("jsonschema")
    schema = {"type": ["object", "array"], "items": {"type": "string"}}
    raw = '{"a", "b"}'

    assert repair_json(
        raw,
        schema=schema,
        skip_json_loads=True,
        return_objects=True,
        schema_repair_mode="salvage",
    ) == ["a", "b"]


def test_schema_salvage_mode_set_like_members_still_fail_incompatible_object_schema():
    pytest.importorskip("jsonschema")
    schema = {
        "type": "object",
        "properties": {"count": {"type": "integer"}},
        "required": ["count"],
    }
    raw = '{"a", "b"}'

    with pytest.raises(ValueError, match="Missing required properties"):
        repair_json(
            raw,
            schema=schema,
            skip_json_loads=True,
            return_objects=True,
            schema_repair_mode="salvage",
        )


def test_schema_salvage_mode_set_like_members_require_string_keys():
    pytest.importorskip("jsonschema")
    schema = {"type": "object"}
    raw = "{1, 2}"

    with pytest.raises(ValueError, match="Expected object"):
        repair_json(
            raw,
            schema=schema,
            skip_json_loads=True,
            return_objects=True,
            schema_repair_mode="salvage",
        )


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


def test_schema_salvage_mode_union_object_array_falls_back_to_valid_array_branch():
    pytest.importorskip("jsonschema")
    schema = {
        "type": ["object", "array"],
        "properties": {"name": {"type": "string", "pattern": "^a+$"}},
        "required": ["name"],
        "items": {"type": "string"},
    }
    raw = '["bbb",]'

    assert repair_json(raw, schema=schema, return_objects=True, schema_repair_mode="standard") == ["bbb"]
    assert repair_json(raw, schema=schema, return_objects=True, schema_repair_mode="salvage") == ["bbb"]


def test_schema_salvage_mode_union_object_array_does_not_remap_valid_array():
    pytest.importorskip("jsonschema")
    schema = {
        "type": ["object", "array"],
        "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}},
        "required": ["x", "y"],
        "items": {"type": "integer"},
    }
    raw = "[1,2]"

    assert repair_json(
        raw,
        schema=schema,
        skip_json_loads=True,
        return_objects=True,
        schema_repair_mode="salvage",
    ) == [1, 2]

    repaired_with_logs, logs = cast(
        "tuple[object, list[dict[str, str]]]",
        repair_json(
            raw,
            schema=schema,
            skip_json_loads=True,
            logging=True,
            schema_repair_mode="salvage",
        ),
    )
    assert repaired_with_logs == [1, 2]
    assert not any(
        log["text"]
        in {
            "Mapped array to object by schema property order",
            "Unwrapped single-item root array to object while salvaging",
        }
        for log in logs
    )


def test_schema_salvage_mode_unwraps_root_single_item_array_and_fills_required_array():
    pytest.importorskip("jsonschema")
    schema = {
        "type": "object",
        "properties": {
            "type": {"const": "food_sport_card"},
            "content": {
                "type": "object",
                "required": ["food", "sports"],
                "properties": {
                    "food": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "sports": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
        },
        "required": ["type", "content"],
    }
    raw = """[
    {
        "type": "food_sport_card",
        "content": {
            "food": [
                "mantou"
            ]
        }
    }
"""

    with pytest.raises(ValueError, match=r"Expected object at \$, got list\."):
        repair_json(
            raw,
            schema=schema,
            return_objects=True,
            schema_repair_mode="standard",
        )

    assert repair_json(
        raw,
        schema=schema,
        return_objects=True,
        schema_repair_mode="salvage",
    ) == {
        "type": "food_sport_card",
        "content": {"food": ["mantou"], "sports": []},
    }

    repaired_with_logs, logs = cast(
        "tuple[object, list[dict[str, str]]]",
        repair_json(
            raw,
            schema=schema,
            logging=True,
            schema_repair_mode="salvage",
        ),
    )
    assert repaired_with_logs == {
        "type": "food_sport_card",
        "content": {"food": ["mantou"], "sports": []},
    }
    assert any(log["text"] == "Unwrapped single-item root array to object while salvaging" for log in logs)
    assert any(
        log["text"] == "Filled missing required property while salvaging" and log["context"] == "$.content.sports"
        for log in logs
    )


def test_schema_salvage_mode_fills_required_with_safe_inference_sources():
    pytest.importorskip("jsonschema")
    schema = {
        "type": "object",
        "properties": {
            "from_default": {"default": "x"},
            "from_const": {"const": 7},
            "from_enum": {"enum": ["first", "second"]},
            "from_array_shape": {"items": {"type": "integer"}},
            "from_object_shape": {"properties": {"nested": {"type": "string"}}},
        },
        "required": [
            "from_default",
            "from_const",
            "from_enum",
            "from_array_shape",
            "from_object_shape",
        ],
    }
    assert repair_json(
        "{}",
        schema=schema,
        return_objects=True,
        schema_repair_mode="salvage",
    ) == {
        "from_default": "x",
        "from_const": 7,
        "from_enum": "first",
        "from_array_shape": [],
        "from_object_shape": {},
    }


def test_schema_salvage_mode_missing_required_without_property_schema_still_raises():
    pytest.importorskip("jsonschema")
    schema = {"type": "object", "properties": {}, "required": ["missing"]}
    with pytest.raises(ValueError, match="Missing required properties"):
        repair_json(
            "{}",
            schema=schema,
            return_objects=True,
            schema_repair_mode="salvage",
        )


def test_schema_salvage_mode_missing_required_boolean_schema_still_raises():
    pytest.importorskip("jsonschema")
    schema = {
        "type": "object",
        "properties": {"payload": True},
        "required": ["payload"],
    }
    with pytest.raises(ValueError, match="Missing required properties"):
        repair_json(
            "{}",
            schema=schema,
            return_objects=True,
            schema_repair_mode="salvage",
        )


def test_schema_salvage_mode_root_unwrap_requires_single_item():
    pytest.importorskip("jsonschema")
    schema = {
        "type": "object",
        "properties": {"value": {"type": "integer"}},
        "required": ["value"],
    }
    with pytest.raises(ValueError, match=r"Expected object at \$, got list\."):
        repair_json(
            '[{"value": 1}, {"value": 2}]',
            schema=schema,
            return_objects=True,
            schema_repair_mode="salvage",
        )


def test_schema_salvage_mode_missing_required_scalar_still_raises():
    pytest.importorskip("jsonschema")
    schema = {
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
    }
    with pytest.raises(ValueError, match="Missing required properties"):
        repair_json(
            "[{}]",
            schema=schema,
            return_objects=True,
            schema_repair_mode="salvage",
        )


def test_schema_salvage_mode_requires_schema():
    with pytest.raises(ValueError, match="schema_repair_mode"):
        repair_json("{}", return_objects=True, schema_repair_mode="salvage")
