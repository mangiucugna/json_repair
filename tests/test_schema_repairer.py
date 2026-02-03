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
    with pytest.raises(ValueError, match="Expected boolean"):
        repairer._coerce_scalar("yes", "boolean", "$")
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
