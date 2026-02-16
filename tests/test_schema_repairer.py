import copy
from typing import Any, ClassVar

import pytest

from src.json_repair import repair_json
from src.json_repair.schema_repair import (
    SchemaRepairer,
    load_schema_model,
    normalize_missing_values,
    schema_from_input,
)
from src.json_repair.utils.constants import MISSING_VALUE


def test_missing_value_deepcopy():
    assert copy.deepcopy(MISSING_VALUE) is MISSING_VALUE


def test_normalize_missing_values_nested_and_invalid():
    assert normalize_missing_values(MISSING_VALUE) == ""
    assert normalize_missing_values({"a": MISSING_VALUE, "b": [MISSING_VALUE, 1]}) == {"a": "", "b": ["", 1]}
    with pytest.raises(ValueError, match="Object keys must be strings"):
        normalize_missing_values({1: "a"})
    with pytest.raises(ValueError, match="JSON compatible"):
        normalize_missing_values(object())


def test_load_schema_model_errors_and_success(tmp_path, monkeypatch):
    with pytest.raises(ValueError, match="Schema model must be in the form"):
        load_schema_model("invalid")

    module_path = tmp_path / "schema_mod.py"
    module_path.write_text("class SchemaModel:\n    pass\n")
    monkeypatch.syspath_prepend(tmp_path)

    assert load_schema_model("schema_mod:SchemaModel").__name__ == "SchemaModel"
    with pytest.raises(ValueError, match="not found"):
        load_schema_model("schema_mod:Missing")


def test_schema_from_input_basic_and_invalid():
    assert schema_from_input({"type": "string"}) == {"type": "string"}
    assert schema_from_input(True) is True
    assert schema_from_input(False) is False
    with pytest.raises(ValueError, match="Schema must be a JSON Schema"):
        schema_from_input(1)


def test_schema_from_input_model_defaults_and_required():
    pydantic = pytest.importorskip("pydantic")
    version = getattr(pydantic, "VERSION", getattr(pydantic, "__version__", "0"))
    if int(version.split(".")[0]) < 2:
        pytest.skip("pydantic v2 required")

    class DummyField:
        def __init__(self, default, default_factory=None, required=False):
            self.default = default
            self.default_factory = default_factory
            self._required = required

        def is_required(self):
            return self._required

    class DummyModel:
        @staticmethod
        def model_json_schema():
            return {"properties": {"name": "not-a-dict"}}

        model_fields: ClassVar[dict[str, DummyField]] = {
            "name": DummyField(default="x"),
            "items": DummyField(default=None, default_factory=lambda: ["a"]),
            "required_field": DummyField(default="y", required=True),
        }

    schema = schema_from_input(DummyModel)
    assert isinstance(schema, dict)
    assert schema["properties"]["name"]["default"] == "x"
    assert schema["properties"]["items"]["default"] == ["a"]
    assert "required_field" not in schema["properties"]

    class DummyModelWithDefaults:
        @staticmethod
        def model_json_schema():
            return {"properties": {"name": {"default": "keep"}}}

        model_fields: ClassVar[dict[str, DummyField]] = {"name": DummyField(default="x")}

    schema_with_default = schema_from_input(DummyModelWithDefaults)
    assert isinstance(schema_with_default, dict)
    assert schema_with_default["properties"]["name"]["default"] == "keep"


def test_schema_from_input_non_dict_properties():
    pydantic = pytest.importorskip("pydantic")
    version = getattr(pydantic, "VERSION", getattr(pydantic, "__version__", "0"))
    if int(version.split(".")[0]) < 2:
        pytest.skip("pydantic v2 required")

    class DummyField:
        def __init__(self, default):
            self.default = default
            self.default_factory = None

        def is_required(self):
            return False

    class DummyModel:
        @staticmethod
        def model_json_schema():
            return {"properties": []}

        model_fields: ClassVar[dict[str, DummyField]] = {"value": DummyField(default=1)}

    schema = schema_from_input(DummyModel)
    assert isinstance(schema, dict)
    assert schema["properties"]["value"]["default"] == 1


def test_schema_from_input_requires_pydantic_v2(monkeypatch):
    pydantic = pytest.importorskip("pydantic")
    monkeypatch.setattr(pydantic, "VERSION", "1.0")

    class DummyModel:
        @staticmethod
        def model_json_schema():
            return {}

    with pytest.raises(ValueError, match="pydantic v2"):
        schema_from_input(DummyModel)


def test_schema_repairer_validate_and_prepare():
    pytest.importorskip("jsonschema")
    repairer = SchemaRepairer({}, [])
    repairer.validate(1, True)
    with pytest.raises(ValueError, match="Schema does not allow"):
        repairer.validate(1, False)
    repairer.validate(1, {"type": "integer"})
    with pytest.raises(ValueError, match="is not of type"):
        repairer.validate("x", {"type": "integer"})

    schema = {
        "type": "array",
        "items": [{"type": "integer"}, {"type": "string"}],
        "additionalItems": False,
    }
    repairer.validate([1, "a"], schema)
    prepared = repairer._prepare_schema_for_validation(schema)
    assert prepared["prefixItems"]
    assert prepared["items"] is False

    schema2 = {
        "items": [{"type": "integer"}],
        "additionalItems": {"type": "string"},
    }
    prepared2 = repairer._prepare_schema_for_validation(schema2)
    assert prepared2["items"] == {"type": "string"}

    invalid_schema: Any = True
    with pytest.raises(ValueError, match="Schema must be an object"):
        repairer._prepare_schema_for_validation(invalid_schema)


def test_schema_repairer_resolve_schema_and_refs():
    root = {"defs": {"node": {"type": "string"}}, "flag": True, "flag_false": False, "bad": 1}
    repairer = SchemaRepairer(root, None)
    assert repairer.resolve_schema(None) is True
    assert repairer.resolve_schema(False) is False
    assert repairer.resolve_schema({"$ref": "#/defs/node"}) == {"type": "string"}
    assert repairer.resolve_schema({"$ref": "#/flag"}) is True
    assert repairer.resolve_schema({"$ref": "#/flag_false"}) is False
    invalid_schema: Any = "nope"
    with pytest.raises(ValueError, match="Schema must be an object"):
        repairer.resolve_schema(invalid_schema)
    with pytest.raises(ValueError, match="Schema keys must be strings"):
        repairer.resolve_schema({1: "bad"})

    with pytest.raises(ValueError, match="Unsupported \\$ref"):
        repairer._resolve_ref("http://example.com")
    with pytest.raises(ValueError, match="Unresolvable \\$ref"):
        repairer._resolve_ref("#/missing")
    with pytest.raises(ValueError, match="Unresolvable \\$ref"):
        repairer._resolve_ref("#/bad")


def test_schema_repairer_copy_json_value_edges():
    repairer = SchemaRepairer({}, [])
    assert repairer._copy_json_value({"a": {"b": 1}}, "$", "default") == {"a": {"b": 1}}
    with pytest.raises(ValueError, match="non-string key"):
        repairer._copy_json_value({1: "a"}, "$", "default")
    with pytest.raises(ValueError, match="not JSON compatible"):
        repairer._copy_json_value(object(), "$", "default")


def test_schema_repairer_object_and_array_helpers():
    repairer = SchemaRepairer({}, None)
    assert repairer.is_object_schema({"type": "object"}) is True
    assert repairer.is_object_schema({"type": ["null", "object"]}) is True
    assert repairer.is_object_schema({"properties": {}}) is True
    assert repairer.is_object_schema({"type": "string"}) is False

    assert repairer.is_array_schema({"type": "array"}) is True
    assert repairer.is_array_schema({"type": ["array", "null"]}) is True
    assert repairer.is_array_schema({"items": {"type": "string"}}) is True
    assert repairer.is_array_schema({"type": "object"}) is False

    assert repairer.is_object_schema(True) is False
    assert repairer.is_array_schema(False) is False


def test_repair_value_missing_and_unions():
    repairer = SchemaRepairer({}, [])
    assert repairer.repair_value(MISSING_VALUE, {"const": 1}, "$") == 1
    assert repairer.repair_value(MISSING_VALUE, {"enum": [2, 3]}, "$") == 2
    assert repairer.repair_value(MISSING_VALUE, {"default": "x"}, "$") == "x"
    assert repairer.repair_value(MISSING_VALUE, {"type": "string"}, "$") == ""

    schema_any = {"anyOf": [{"type": "integer"}, {"type": "string"}]}
    assert repairer.repair_value("1", schema_any, "$") == 1

    schema_one = {"oneOf": [{"type": "integer"}, {"type": "boolean"}]}
    with pytest.raises(ValueError, match="Expected boolean"):
        repairer.repair_value("nope", schema_one, "$")

    schema_all = {"allOf": [{"type": "string"}, {"enum": ["a"]}]}
    assert repairer.repair_value("a", schema_all, "$") == "a"
    with pytest.raises(ValueError, match="does not match enum"):
        repairer.repair_value("b", schema_all, "$")

    schema_union = {"type": ["integer", "string"]}
    assert repairer.repair_value("2", schema_union, "$") == 2

    with pytest.raises(ValueError, match="No schema matched"):
        repairer.repair_value("x", {"oneOf": []}, "$")
    with pytest.raises(ValueError, match="Expected boolean"):
        repairer.repair_value("x", {"type": ["integer", "boolean"]}, "$")
    with pytest.raises(ValueError, match="No schema type matched"):
        repairer.repair_value("x", {"type": []}, "$")

    schema_array_union = {"type": ["array", "string"], "items": {"type": "integer"}}
    assert repairer.repair_value(["1"], schema_array_union, "$") == [1]
    schema_obj_union = {"type": ["object", "string"], "properties": {"a": {"type": "integer"}}}
    assert repairer.repair_value({"a": "1"}, schema_obj_union, "$") == {"a": 1}


def test_repair_object_and_array_paths():
    repairer = SchemaRepairer({}, [])
    schema_obj = {
        "type": "object",
        "properties": {
            "a": {"type": "integer"},
            "b": {"type": "string", "default": "x"},
        },
        "required": ["a"],
        "patternProperties": {
            "^x": {"type": "integer"},
            "1$": {"type": "integer"},
        },
        "additionalProperties": False,
    }
    value = {"a": "1", "x1": "2", "extra": "drop"}
    assert repairer.repair_value(value, schema_obj, "$") == {"a": 1, "b": "x", "x1": 2}
    with pytest.raises(ValueError, match="Missing required properties"):
        repairer.repair_value({}, schema_obj, "$")

    schema_obj_extra = {"type": "object", "additionalProperties": {"type": "integer"}}
    assert repairer.repair_value({"a": "1"}, schema_obj_extra, "$") == {"a": 1}

    schema_min_props = {"type": "object", "minProperties": 1}
    with pytest.raises(ValueError, match="minProperties"):
        repairer.repair_value({}, schema_min_props, "$")

    schema_bad_props = {"type": "object", "properties": [], "patternProperties": []}
    assert repairer.repair_value({}, schema_bad_props, "$") == {}
    with pytest.raises(ValueError, match="Expected object"):
        repairer.repair_value([], {"type": "object"}, "$")

    schema_array = {
        "type": "array",
        "items": [{"type": "integer"}],
        "additionalItems": False,
    }
    assert repairer.repair_value([1, 2], schema_array, "$") == [1]
    schema_tuple = {"type": "array", "items": [{"type": "integer"}, {"type": "string"}]}
    assert repairer.repair_value([1], schema_tuple, "$") == [1]

    schema_array_extra = {
        "type": "array",
        "items": [{"type": "integer"}],
        "additionalItems": {"type": "string"},
    }
    assert repairer.repair_value([1, 2], schema_array_extra, "$") == [1, "2"]

    schema_array_open = {
        "type": "array",
        "items": [{"type": "integer"}],
        "additionalItems": True,
    }
    assert repairer.repair_value([1, "x"], schema_array_open, "$") == [1, "x"]

    schema_array_items = {"type": "array", "items": {"type": "integer"}}
    assert repairer.repair_value(["1", 2], schema_array_items, "$") == [1, 2]

    schema_array_wrap = {"type": "array"}
    assert repairer.repair_value("a", schema_array_wrap, "$") == ["a"]

    schema_min_items = {"type": "array", "minItems": 1}
    with pytest.raises(ValueError, match="minItems"):
        repairer.repair_value([], schema_min_items, "$")


def test_fill_missing_and_coerce_scalar_paths():
    repairer = SchemaRepairer({}, [])
    assert repairer._fill_missing({"type": "integer"}, "$") == 0
    assert repairer._fill_missing({"type": "number"}, "$") == 0
    assert repairer._fill_missing({"type": "boolean"}, "$") is False
    assert repairer._fill_missing({"type": "null"}, "$") is None
    assert repairer._fill_missing({"type": "array"}, "$") == []
    assert repairer._fill_missing({"type": "object"}, "$") == {}
    assert repairer._fill_missing({"type": ["string", "integer"]}, "$") == ""
    assert repairer._fill_missing({"properties": {"a": {"type": "string"}}}, "$") == {}
    assert repairer._fill_missing({"items": {"type": "string"}}, "$") == []
    with pytest.raises(ValueError, match="requires at least"):
        repairer._fill_missing({"type": "array", "minItems": 1}, "$")
    with pytest.raises(ValueError, match="requires at least"):
        repairer._fill_missing({"type": "object", "minProperties": 1}, "$")
    with pytest.raises(ValueError, match="Cannot infer missing value"):
        repairer._fill_missing({"type": "custom"}, "$")
    with pytest.raises(ValueError, match="has no values"):
        repairer._fill_missing({"enum": []}, "$")
    with pytest.raises(ValueError, match="Cannot infer missing value"):
        repairer._fill_missing({"type": ["unsupported"]}, "$")

    assert repairer._coerce_scalar(1, "string", "$") == "1"
    assert repairer._coerce_scalar("2", "integer", "$") == 2
    assert repairer._coerce_scalar("2.0", "integer", "$") == 2
    assert repairer._coerce_scalar(2.0, "integer", "$") == 2
    assert repairer._coerce_scalar("2.5", "number", "$") == 2.5
    assert repairer._coerce_scalar("true", "boolean", "$") is True
    assert repairer._coerce_scalar("false", "boolean", "$") is False
    assert repairer._coerce_scalar(None, "null", "$") is None

    with pytest.raises(ValueError, match="Expected string"):
        repairer._coerce_scalar(True, "string", "$")
    with pytest.raises(ValueError, match="Expected integer"):
        repairer._coerce_scalar(True, "integer", "$")
    with pytest.raises(ValueError, match="Expected integer"):
        repairer._coerce_scalar(2.5, "integer", "$")
    with pytest.raises(ValueError, match="Expected integer"):
        repairer._coerce_scalar("2.5", "integer", "$")
    with pytest.raises(ValueError, match="Expected integer"):
        repairer._coerce_scalar({}, "integer", "$")
    with pytest.raises(ValueError, match="Expected number"):
        repairer._coerce_scalar(True, "number", "$")
    with pytest.raises(ValueError, match="Expected number"):
        repairer._coerce_scalar("nope", "number", "$")
    with pytest.raises(ValueError, match="Expected number"):
        repairer._coerce_scalar([], "number", "$")
    assert repairer._coerce_scalar("yes", "boolean", "$") is True
    assert repairer._coerce_scalar("Yes", "boolean", "$") is True
    assert repairer._coerce_scalar("no", "boolean", "$") is False
    assert repairer._coerce_scalar("No", "boolean", "$") is False
    assert repairer._coerce_scalar("1", "boolean", "$") is True
    assert repairer._coerce_scalar("0", "boolean", "$") is False
    assert repairer._coerce_scalar(1, "boolean", "$") is True
    assert repairer._coerce_scalar(0, "boolean", "$") is False
    assert repairer._coerce_scalar(3.14, "boolean", "$") is True
    assert repairer._coerce_scalar(0.0, "boolean", "$") is False
    with pytest.raises(ValueError, match="Expected boolean"):
        repairer._coerce_scalar([], "boolean", "$")
    with pytest.raises(ValueError, match="Expected null"):
        repairer._coerce_scalar("x", "null", "$")
    with pytest.raises(ValueError, match="Unsupported schema type"):
        repairer._coerce_scalar("x", "unsupported", "$")

    assert repairer.repair_value({"a": MISSING_VALUE}, {}, "$") == {"a": ""}
    assert repairer.repair_value({"a": MISSING_VALUE}, {"allOf": []}, "$") == {"a": ""}
    assert repairer.repair_value({"a": "1"}, {"properties": {"a": {"type": "integer"}}}, "$") == {"a": 1}
    assert repairer.repair_value(["1"], {"items": {"type": "integer"}}, "$") == [1]
    with pytest.raises(ValueError, match="Schema does not allow"):
        repairer.repair_value(1, False, "$")


def test_apply_enum_const_mismatch_raises():
    repairer = SchemaRepairer({}, [])
    with pytest.raises(ValueError, match="does not match const"):
        repairer.repair_value("b", {"const": "a"}, "$")
    with pytest.raises(ValueError, match="does not match enum"):
        repairer.repair_value("b", {"enum": ["a"]}, "$")


def test_repair_json_valid_empty_string_returns_empty():
    assert repair_json('""') == ""


def test_map_list_to_object_unambiguous():
    """List elements are mapped to object properties when exactly one candidate exists."""
    pytest.importorskip("jsonschema")
    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "tags": {"type": "array", "items": {"type": "string"}},
            "meta": {
                "type": "object",
                "properties": {"k": {"type": "string"}},
            },
        },
    }
    repairer = SchemaRepairer(schema, [], enable_shape_fixes=True)
    # Each element type has exactly one matching property.
    value = ["hello", ["a", "b"], {"k": "v"}]
    result = repairer.repair_value(value, schema, "$")
    assert result == {"name": "hello", "tags": ["a", "b"], "meta": {"k": "v"}}


def test_map_list_to_object_ambiguous_returns_error():
    """When multiple candidates match, the mapping is ambiguous and we raise."""
    pytest.importorskip("jsonschema")
    schema = {
        "type": "object",
        "properties": {
            "first_name": {"type": "string"},
            "last_name": {"type": "string"},
        },
    }
    repairer = SchemaRepairer(schema, [], enable_shape_fixes=True)
    # Two string properties → ambiguous for a single string element.
    with pytest.raises(ValueError, match="Expected object"):
        repairer.repair_value(["hello"], schema, "$")


def test_map_list_to_object_number_and_bool():
    """Number and boolean elements are mapped to appropriate schema properties."""
    pytest.importorskip("jsonschema")
    schema = {
        "type": "object",
        "properties": {
            "count": {"type": "integer"},
            "active": {"type": "boolean"},
        },
    }
    repairer = SchemaRepairer(schema, [], enable_shape_fixes=True)
    result = repairer.repair_value([42, True], schema, "$")
    assert result == {"count": 42, "active": True}


def test_map_list_to_object_disabled_by_default():
    """Without enable_shape_fixes, list→object mapping does not happen."""
    schema = {
        "type": "object",
        "properties": {"name": {"type": "string"}},
    }
    repairer = SchemaRepairer(schema, [])
    with pytest.raises(ValueError, match="Expected object"):
        repairer.repair_value(["hello"], schema, "$")


def test_map_list_to_object_empty_properties():
    """When schema has no properties, list mapping returns None and raises."""
    schema = {"type": "object"}
    repairer = SchemaRepairer(schema, [], enable_shape_fixes=True)
    with pytest.raises(ValueError, match="Expected object"):
        repairer.repair_value(["hello"], schema, "$")


def test_unwrap_single_key_object():
    """A single-key wrapper dict is unwrapped when the inner dict has all required keys."""
    pytest.importorskip("jsonschema")
    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "age": {"type": "integer"},
        },
        "required": ["name", "age"],
    }
    repairer = SchemaRepairer(schema, [], enable_shape_fixes=True)
    value = {"result": {"name": "Alice", "age": 30}}
    result = repairer.repair_value(value, schema, "$")
    assert result == {"name": "Alice", "age": 30}


def test_unwrap_single_key_object_outer_key_is_property():
    """No unwrapping when the outer key is a declared schema property."""
    pytest.importorskip("jsonschema")
    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "object"},
        },
    }
    repairer = SchemaRepairer(schema, [], enable_shape_fixes=True)
    value = {"name": {"inner": "data"}}
    # "name" IS a property, so no unwrapping; should repair normally.
    result = repairer.repair_value(value, schema, "$")
    assert result == {"name": {"inner": "data"}}


def test_unwrap_single_key_object_missing_required():
    """No unwrapping when the inner dict is missing required keys."""
    pytest.importorskip("jsonschema")
    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "age": {"type": "integer"},
        },
        "required": ["name", "age"],
    }
    repairer = SchemaRepairer(schema, [], enable_shape_fixes=True)
    # Inner dict only has "name", missing "age" → no unwrap, treated as missing required.
    with pytest.raises(ValueError, match="Missing required properties"):
        repairer.repair_value({"wrapper": {"name": "Alice"}}, schema, "$")


def test_unwrap_single_key_object_multi_key():
    """No unwrapping when the dict has multiple keys."""
    pytest.importorskip("jsonschema")
    schema = {
        "type": "object",
        "properties": {"a": {"type": "string"}, "b": {"type": "string"}},
        "required": ["a", "b"],
    }
    repairer = SchemaRepairer(schema, [], enable_shape_fixes=True)
    value = {"a": "x", "b": "y"}
    result = repairer.repair_value(value, schema, "$")
    assert result == {"a": "x", "b": "y"}


def test_unwrap_single_key_inner_not_dict():
    """No unwrapping when the inner value is not a dict."""
    schema = {
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
    }
    repairer = SchemaRepairer(schema, [], enable_shape_fixes=True)
    with pytest.raises(ValueError, match="Missing required properties"):
        repairer.repair_value({"wrapper": "not-a-dict"}, schema, "$")


def test_unwrap_disabled_by_default():
    """Without enable_shape_fixes, single-key unwrapping does not happen."""
    schema = {
        "type": "object",
        "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
        "required": ["name", "age"],
    }
    repairer = SchemaRepairer(schema, [])
    with pytest.raises(ValueError, match="Missing required properties"):
        repairer.repair_value({"result": {"name": "Alice", "age": 30}}, schema, "$")


def test_shape_fixes_via_repair_json_fast_path():
    """Shape fixes work through the full repair_json API on the fast path (valid JSON)."""
    pytest.importorskip("jsonschema")
    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "age": {"type": "integer"},
        },
        "required": ["name", "age"],
    }
    # Valid JSON (parseable by json.loads), but wrong shape — needs unwrapping.
    raw = '{"result": {"name": "Alice", "age": 30}}'
    result = repair_json(raw, return_objects=True, schema=schema, enable_shape_fixes=True)
    assert result == {"name": "Alice", "age": 30}


def test_shape_fixes_via_repair_json_skip_json_loads():
    """Shape fixes work through the full repair_json API on the parser path."""
    pytest.importorskip("jsonschema")
    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "tags": {"type": "array", "items": {"type": "string"}},
        },
    }
    raw = '["hello", ["a", "b"]]'
    result = repair_json(raw, return_objects=True, schema=schema, enable_shape_fixes=True, skip_json_loads=True)
    assert result == {"name": "hello", "tags": ["a", "b"]}


def test_shape_fixes_logging():
    """Shape-fix log entries appear when logging is enabled."""
    pytest.importorskip("jsonschema")
    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "age": {"type": "integer"},
        },
        "required": ["name", "age"],
    }
    raw = '{"wrapper": {"name": "Alice", "age": 30}}'
    result, logs = repair_json(raw, return_objects=True, schema=schema, enable_shape_fixes=True, logging=True)
    assert result == {"name": "Alice", "age": 30}
    log_texts = [entry["text"] for entry in logs]
    assert any("Unwrapped" in t for t in log_texts)


def test_array_invalid_items_raise_by_default():
    """By default, array items that cannot be repaired raise instead of being dropped."""
    repairer = SchemaRepairer({}, [])
    schema = {"type": "array", "items": {"type": "integer"}}
    with pytest.raises(ValueError, match="Expected integer"):
        repairer.repair_value([1, "abc", "3", 4], schema, "$")


def test_array_drops_invalid_items_when_enabled():
    """With drop_invalid_items, array items that cannot be repaired are dropped."""
    repairer = SchemaRepairer({}, [], drop_invalid_items=True)
    schema = {"type": "array", "items": {"type": "integer"}}
    assert repairer.repair_value([1, "abc", "3", 4], schema, "$") == [1, 3, 4]


def test_array_drops_invalid_items_logging():
    """Dropped array items are logged."""
    log: list[dict[str, str]] = []
    repairer = SchemaRepairer({}, log, drop_invalid_items=True)
    schema = {"type": "array", "items": {"type": "integer"}}
    result = repairer.repair_value([1, "abc", 3], schema, "$")
    assert result == [1, 3]
    assert any("Dropped invalid array item" in entry["text"] for entry in log)


def test_object_coercion_failure_propagates():
    """When a property value can't be repaired, the error propagates even if a default exists."""
    repairer = SchemaRepairer({}, [])
    schema = {
        "type": "object",
        "properties": {
            "level": {"type": "number", "default": 1},
        },
    }
    with pytest.raises(ValueError, match="Expected number"):
        repairer.repair_value({"level": "intermediate"}, schema, "$")


def test_missing_required_with_default():
    """Missing required properties that have defaults are filled instead of raising."""
    repairer = SchemaRepairer({}, [])
    schema = {
        "type": "object",
        "properties": {
            "id": {"type": "number", "default": 0},
            "name": {"type": "string"},
        },
        "required": ["id", "name"],
    }
    result = repairer.repair_value({"name": "test"}, schema, "$")
    assert result == {"id": 0, "name": "test"}


def test_missing_required_without_default_still_raises():
    """Missing required properties without defaults still raise."""
    repairer = SchemaRepairer({}, [])
    schema = {
        "type": "object",
        "properties": {
            "id": {"type": "number"},
            "name": {"type": "string"},
        },
        "required": ["id", "name"],
    }
    with pytest.raises(ValueError, match="Missing required properties"):
        repairer.repair_value({"name": "test"}, schema, "$")


def test_shape_fix_unwrap_dict_to_array():
    """Shape fix: unwrap {key: [...]} to [...] when schema expects array."""
    schema = {
        "type": "array",
        "items": {"type": "string"},
    }
    repairer = SchemaRepairer(schema, [], enable_shape_fixes=True)
    result = repairer.repair_value({"items": ["a", "b", "c"]}, schema, "$")
    assert result == ["a", "b", "c"]


def test_shape_fix_unwrap_dict_to_array_non_list_value():
    """Shape fix: when dict has one key but value is not a list, wrap dict in an array."""
    schema = {"type": "array"}
    repairer = SchemaRepairer(schema, [], enable_shape_fixes=True)
    # sole value is not a list → falls through to normal wrap behavior
    result = repairer.repair_value({"key": "value"}, schema, "$")
    assert result == [{"key": "value"}]


def test_shape_fix_unwrap_dict_to_array_disabled():
    """Without enable_shape_fixes, dict→array unwrapping wraps the dict in an array."""
    schema = {"type": "array"}
    repairer = SchemaRepairer(schema, [])
    result = repairer.repair_value({"items": ["a"]}, schema, "$")
    assert result == [{"items": ["a"]}]


def test_shape_fix_unwrap_dict_to_scalar():
    """Shape fix: unwrap {key: value} to value when schema expects a scalar type."""
    schema_str = {"type": "string"}
    repairer = SchemaRepairer(schema_str, [], enable_shape_fixes=True)
    assert repairer.repair_value({"result": "hello"}, schema_str, "$") == "hello"

    schema_num = {"type": "number"}
    repairer_num = SchemaRepairer(schema_num, [], enable_shape_fixes=True)
    assert repairer_num.repair_value({"count": 42}, schema_num, "$") == 42

    schema_bool = {"type": "boolean"}
    repairer_bool = SchemaRepairer(schema_bool, [], enable_shape_fixes=True)
    assert repairer_bool.repair_value({"flag": True}, schema_bool, "$") is True


def test_shape_fix_unwrap_dict_to_scalar_with_coercion():
    """Shape fix unwrapping combined with type coercion."""
    schema = {"type": "integer"}
    repairer = SchemaRepairer(schema, [], enable_shape_fixes=True)
    # Unwraps the dict, then coerces string "42" to integer 42
    assert repairer.repair_value({"value": "42"}, schema, "$") == 42


def test_shape_fix_unwrap_dict_to_scalar_container_not_unwrapped():
    """Shape fix does not unwrap dicts whose sole value is a container."""
    schema = {"type": "string"}
    repairer = SchemaRepairer(schema, [], enable_shape_fixes=True)
    # sole value is a dict → not unwrapped → raises
    with pytest.raises(ValueError, match="Expected string"):
        repairer.repair_value({"result": {"inner": "value"}}, schema, "$")
    # sole value is a list → not unwrapped → raises
    with pytest.raises(ValueError, match="Expected string"):
        repairer.repair_value({"result": [1, 2]}, schema, "$")


def test_shape_fix_unwrap_dict_to_scalar_disabled():
    """Without enable_shape_fixes, dict→scalar unwrapping does not happen."""
    schema = {"type": "string"}
    repairer = SchemaRepairer(schema, [])
    with pytest.raises(ValueError, match="Expected string"):
        repairer.repair_value({"result": "hello"}, schema, "$")


def test_complex_schema_repair_integration():
    """Complex integration test exercising multiple repair features together,
    inspired by real-world LLM output repair scenarios."""
    pytest.importorskip("jsonschema")
    schema = {
        "type": "object",
        "properties": {
            "user": {
                "type": "object",
                "properties": {
                    "id": {"type": "number"},
                    "name": {"type": "string"},
                    "active": {"type": "boolean", "default": True},
                    "profile": {
                        "type": "object",
                        "properties": {
                            "age": {"type": "number"},
                            "bio": {"type": "string", "default": "No bio provided"},
                            "level": {"type": "number", "default": 1},
                        },
                        "additionalProperties": False,
                    },
                    "preferences": {
                        "type": "object",
                        "properties": {
                            "theme": {"type": "string", "default": "light"},
                            "notifications": {"type": "boolean", "default": True},
                            "language": {"type": "string", "default": "en"},
                        },
                        "additionalProperties": False,
                    },
                    "permissions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "resource": {"type": "string"},
                                "access_level": {"type": "string"},
                            },
                            "required": ["resource", "access_level"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["id", "name"],
                "additionalProperties": False,
            },
            "posts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "number", "default": 0},
                        "title": {"type": "string"},
                        "content": {"type": "string"},
                        "published": {"type": "boolean", "default": False},
                        "tags": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["id", "title"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["user"],
    }
    value = {
        "user": {
            "id": "123",
            "name": 456,
            "extra_field": "remove me",
            "profile": {
                "age": "29",
                "level": "5",
                "extra": "drop",
            },
            "preferences": {
                "notifications": 0,
                "extra_pref": "remove",
            },
            "permissions": {
                "resource": "api",
                "access_level": "read",
            },
        },
        "posts": [
            {
                "id": "1",
                "title": "First Post",
                "content": 12345,
                "published": "true",
                "tags": "tag1",
            },
            {
                "title": "Second Post",
                "extra_post_field": "remove me",
            },
        ],
    }
    repairer = SchemaRepairer(schema, [])
    result = repairer.repair_value(value, schema, "$")
    expected = {
        "user": {
            "id": 123.0,
            "name": "456",
            "active": True,
            "profile": {
                "age": 29.0,
                "bio": "No bio provided",
                "level": 5.0,
            },
            "preferences": {
                "theme": "light",
                "notifications": False,
                "language": "en",
            },
            "permissions": [{"resource": "api", "access_level": "read"}],
        },
        "posts": [
            {
                "id": 1.0,
                "title": "First Post",
                "content": "12345",
                "published": True,
                "tags": ["tag1"],
            },
            {"id": 0, "title": "Second Post", "published": False},
        ],
    }
    assert result == expected
    # Verify the result validates against the schema
    repairer.validate(result, schema)


def test_complex_repair_via_repair_json():
    """Integration test exercising the full repair_json API with schema-driven repair."""
    pytest.importorskip("jsonschema")
    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "score": {"type": "number"},
            "active": {"type": "boolean"},
            "tags": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["name"],
    }
    raw = '{"name": 42, "score": "99.5", "active": "yes", "tags": "python"}'
    result = repair_json(raw, return_objects=True, schema=schema)
    assert result == {"name": "42", "score": 99.5, "active": True, "tags": ["python"]}
