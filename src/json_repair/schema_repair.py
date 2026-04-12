from __future__ import annotations

import copy
import importlib
from typing import Any, Literal, cast

from .parser_schema import array_schema_config, object_schema_config
from .utils.constants import MISSING_VALUE, JSONReturnType, MissingValueType
from .utils.pattern_properties import match_pattern_properties

SchemaRepairMode = Literal["standard", "salvage"]
SUPPORTED_SCHEMA_REPAIR_MODES: tuple[SchemaRepairMode, ...] = ("standard", "salvage")


class SchemaDefinitionError(ValueError):
    """Raised when schema metadata is invalid or unsupported."""


def normalize_schema_repair_mode(mode: str | None) -> SchemaRepairMode:
    if mode is None:
        return "standard"
    if mode == "standard":
        return "standard"
    if mode == "salvage":
        return "salvage"
    expected = ", ".join(SUPPORTED_SCHEMA_REPAIR_MODES)
    raise ValueError(f"schema_repair_mode must be one of: {expected}.")


def _require_jsonschema() -> Any:
    try:
        return importlib.import_module("jsonschema")
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise ValueError("jsonschema is required when using schema-aware repair.") from exc


def _require_pydantic() -> Any:
    try:
        return importlib.import_module("pydantic")
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise ValueError("pydantic is required when using schema models.") from exc


def _prepare_schema_for_validation_node(node: Any) -> Any:
    if isinstance(node, dict):
        normalized = {key: _prepare_schema_for_validation_node(value) for key, value in node.items()}
        items = normalized.get("items")
        if isinstance(items, list):
            normalized.pop("items", None)
            normalized["prefixItems"] = items
            additional_items = normalized.pop("additionalItems", None)
            if additional_items is False:
                normalized["items"] = False
            elif isinstance(additional_items, dict):
                normalized["items"] = additional_items
        return normalized
    if isinstance(node, list):
        return [_prepare_schema_for_validation_node(item) for item in node]
    return node


def load_schema_model(path: str) -> type[Any]:
    if ":" not in path:
        raise ValueError("Schema model must be in the form 'module:ClassName'.")
    module_name, class_name = path.split(":", 1)
    module = importlib.import_module(module_name)
    model: object | None = module.__dict__.get(class_name)
    if model is None or not isinstance(model, type):
        raise ValueError(f"Schema model '{class_name}' not found in module '{module_name}'.")
    return model


def normalize_missing_values(value: object) -> JSONReturnType:
    if value is MISSING_VALUE or isinstance(value, MissingValueType):
        return ""
    if isinstance(value, dict):
        normalized: dict[str, JSONReturnType] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("Object keys must be strings.")
            normalized[key] = normalize_missing_values(item)
        return normalized
    if isinstance(value, list):
        return [normalize_missing_values(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise ValueError("Value is not JSON compatible.")


def schema_from_input(schema: Any) -> dict[str, Any] | bool:
    if isinstance(schema, dict):
        return schema
    if schema is True or schema is False:
        return schema
    if hasattr(schema, "model_json_schema"):
        pydantic = _require_pydantic()
        version = getattr(pydantic, "VERSION", getattr(pydantic, "__version__", "0"))
        if int(version.split(".")[0]) < 2:
            raise ValueError("pydantic v2 is required for schema models.")
        schema_dict: dict[str, Any] = schema.model_json_schema()
        if hasattr(schema, "model_fields"):
            properties = schema_dict.setdefault("properties", {})
            if not isinstance(properties, dict):
                properties = {}
                schema_dict["properties"] = properties
            for name, field in schema.model_fields.items():
                if field.is_required():
                    continue
                property_schema = properties.setdefault(name, {})
                if not isinstance(property_schema, dict):
                    property_schema = {}
                    properties[name] = property_schema
                if "default" in property_schema:
                    continue
                if field.default_factory is not None:
                    property_schema["default"] = field.default_factory()
                else:
                    property_schema["default"] = field.default
        return schema_dict
    raise ValueError("Schema must be a JSON Schema dict, boolean schema, or pydantic v2 model.")


class SchemaRepairer:
    def __init__(
        self,
        schema: dict[str, Any] | bool,
        log: list[dict[str, str]] | None,
        schema_repair_mode: str = "standard",
    ) -> None:
        self.root_schema = schema
        self.log = log
        self.schema_repair_mode = normalize_schema_repair_mode(schema_repair_mode)
        self._validator_cache: dict[int, tuple[dict[str, Any], Any]] = {}

    def _log(self, text: str, path: str) -> None:
        if self.log is not None:
            self.log.append({"text": text, "context": path})

    def _get_validator(self, schema: dict[str, Any]) -> Any:
        cache_key = id(schema)
        cached_validator = self._validator_cache.get(cache_key)
        if cached_validator is not None and cached_validator[0] is schema:
            return cached_validator[1]

        prepared_schema = self._prepare_schema_for_validation(schema)
        jsonschema = _require_jsonschema()
        validator_cls = jsonschema.validators.validator_for(prepared_schema)
        validator = validator_cls(prepared_schema)
        self._validator_cache[cache_key] = (schema, validator)
        return validator

    def is_valid(self, value: JSONReturnType, schema: dict[str, Any] | bool) -> bool:
        schema = self.resolve_schema(schema)
        if schema is True:
            return True
        if schema is False:
            return False
        validator = self._get_validator(schema)
        return bool(validator.is_valid(value))

    def validate(self, value: JSONReturnType, schema: dict[str, Any] | bool) -> None:
        schema = self.resolve_schema(schema)
        if schema is True:
            return
        if schema is False:
            raise ValueError("Schema does not allow any values.")
        jsonschema = _require_jsonschema()
        validator = self._get_validator(schema)
        try:
            validator.validate(value)
        except jsonschema.exceptions.ValidationError as exc:
            raise ValueError(exc.message) from exc

    def resolve_schema(self, schema: object | None) -> dict[str, Any] | bool:
        if schema is None:
            return True
        if isinstance(schema, bool):
            return schema
        if not isinstance(schema, dict):
            raise SchemaDefinitionError("Schema must be an object.")
        schema_dict: dict[str, Any] = {}
        for key, value in schema.items():
            if not isinstance(key, str):
                raise SchemaDefinitionError("Schema keys must be strings.")
            schema_dict[key] = value
        while "$ref" in schema_dict:
            ref = schema_dict["$ref"]
            resolved = self._resolve_ref(ref)
            if isinstance(resolved, bool):
                return resolved
            schema_dict = resolved
        return schema_dict

    def is_object_schema(self, schema: dict[str, Any] | bool | None) -> bool:
        schema = self.resolve_schema(schema)
        if not isinstance(schema, dict):
            return False
        schema_type = schema.get("type")
        if schema_type == "object":
            return True
        if isinstance(schema_type, list) and "object" in schema_type:
            return True
        return any(key in schema for key in ("properties", "patternProperties", "additionalProperties", "required"))

    def is_array_schema(self, schema: dict[str, Any] | bool | None) -> bool:
        schema = self.resolve_schema(schema)
        if not isinstance(schema, dict):
            return False
        schema_type = schema.get("type")
        if schema_type == "array":
            return True
        if isinstance(schema_type, list) and "array" in schema_type:
            return True
        return "items" in schema

    def _allows_schema_type(self, schema: dict[str, Any], schema_type: str) -> bool:
        declared_type = schema.get("type")
        if isinstance(declared_type, str):
            return declared_type == schema_type
        if isinstance(declared_type, list):
            return schema_type in declared_type
        if schema_type == "object":
            return self.is_object_schema(schema)
        # This helper is only used for object/array checks in _can_salvage_list_as_object.
        return self.is_array_schema(schema)

    def _can_salvage_list_as_object(self, schema: dict[str, Any]) -> bool:
        return self._allows_schema_type(schema, "object") and not self._allows_schema_type(schema, "array")

    def repair_value(self, value: Any, schema: dict[str, Any] | bool | None, path: str) -> JSONReturnType:
        """Apply schema rules to a parsed value, including unions, coercions, and defaults."""
        schema = self.resolve_schema(schema)
        if schema is True:
            return normalize_missing_values(value)
        if schema is False:
            raise ValueError("Schema does not allow any values.")
        if not schema:
            return normalize_missing_values(value)

        if value is MISSING_VALUE:
            return self._fill_missing(schema, path)

        if "allOf" in schema:
            subschemas = schema["allOf"]
            if not subschemas:
                return normalize_missing_values(value)
            repaired = self.repair_value(value, subschemas[0], path)
            for subschema in subschemas[1:]:
                repaired = self.repair_value(repaired, subschema, path)
            return repaired

        if "oneOf" in schema:
            return self._repair_union(value, schema["oneOf"], path)
        if "anyOf" in schema:
            return self._repair_union(value, schema["anyOf"], path)

        expected_type = schema.get("type")
        if expected_type is None:
            if self.is_object_schema(schema):
                expected_type = "object"
            elif self.is_array_schema(schema):
                expected_type = "array"

        if isinstance(expected_type, list):
            return self._repair_type_union(value, expected_type, schema, path)

        if expected_type == "object":
            repaired = self._repair_object(value, schema, path)
        elif expected_type == "array":
            repaired = self._repair_array(value, schema, path)
        elif isinstance(expected_type, str):
            repaired = self._coerce_scalar(value, expected_type, path)
        else:
            repaired = normalize_missing_values(value)

        return self._apply_enum_const(repaired, schema, path)

    def _repair_union(self, value: Any, schemas: list[dict[str, Any] | bool], path: str) -> JSONReturnType:
        last_error: Exception | None = None
        for subschema in schemas:
            try:
                candidate = self.repair_value(copy.deepcopy(value), subschema, path)
                self.validate(candidate, subschema)
            except ValueError as exc:
                last_error = exc
            else:
                return candidate
        if last_error:
            raise ValueError(str(last_error)) from last_error
        raise ValueError("No schema matched the value.")

    def _repair_type_union(
        self,
        value: Any,
        types: list[str],
        schema: dict[str, Any],
        path: str,
    ) -> JSONReturnType:
        last_error: Exception | None = None
        for schema_type in types:
            branch_schema = {**schema, "type": schema_type}
            try:
                # Keep structural schema context for repair heuristics, but validate against the narrowed branch type.
                candidate = self._repair_by_type(copy.deepcopy(value), schema_type, schema, path)
                candidate = self._apply_enum_const(candidate, branch_schema, path)
                self.validate(candidate, branch_schema)
            except ValueError as exc:
                last_error = exc
            else:
                return candidate
        if last_error:
            raise ValueError(str(last_error)) from last_error
        raise ValueError("No schema type matched the value.")

    def _repair_by_type(self, value: Any, schema_type: str, schema: dict[str, Any], path: str) -> JSONReturnType:
        if schema_type == "array":
            return self._repair_array(value, schema, path)
        if schema_type == "object":
            return self._repair_object(value, schema, path)
        return self._coerce_scalar(value, schema_type, path)

    def _repair_array(self, value: Any, schema: dict[str, Any], path: str) -> JSONReturnType:
        if isinstance(value, list):
            items: list[JSONReturnType] = value
        else:
            self._log("Wrapped value in array to match schema", path)
            items = [normalize_missing_values(value)]
        salvage_mode = self.schema_repair_mode == "salvage"
        schema_config = array_schema_config(schema)

        def repair_or_drop(raw_item: Any, item_schema: Any, item_path: str) -> tuple[bool, JSONReturnType]:
            try:
                return True, self.repair_value(raw_item, item_schema, item_path)
            except SchemaDefinitionError:
                raise
            except ValueError:
                if not salvage_mode:
                    raise
                self._log("Dropped invalid array item while salvaging", item_path)
                return False, None

        if schema_config.items_schema is not None:
            if isinstance(schema_config.items_schema, list):
                repaired_items: list[JSONReturnType] = []
                for idx, item_schema in enumerate(schema_config.items_schema):
                    if idx >= len(items):
                        break
                    item_path = f"{path}[{idx}]"
                    keep_item, repaired_value = repair_or_drop(items[idx], item_schema, item_path)
                    if keep_item:
                        repaired_items.append(repaired_value)
                if len(items) > len(schema_config.items_schema):
                    tail = items[len(schema_config.items_schema) :]
                    if isinstance(schema_config.additional_items, dict):
                        for offset, item in enumerate(tail, start=len(schema_config.items_schema)):
                            item_path = f"{path}[{offset}]"
                            keep_item, repaired_value = repair_or_drop(item, schema_config.additional_items, item_path)
                            if keep_item:
                                repaired_items.append(repaired_value)
                    elif schema_config.additional_items is True or schema_config.additional_items is None:
                        repaired_items.extend(normalize_missing_values(item) for item in tail)
                    else:
                        for offset, _item in enumerate(tail, start=len(schema_config.items_schema)):
                            self._log("Dropped extra array item not covered by schema", f"{path}[{offset}]")
                items = repaired_items
            else:
                repaired_items = []
                for idx, item in enumerate(items):
                    item_path = f"{path}[{idx}]"
                    keep_item, repaired_value = repair_or_drop(item, schema_config.items_schema, item_path)
                    if keep_item:
                        repaired_items.append(repaired_value)
                items = repaired_items
        min_items = schema.get("minItems")
        if min_items is not None and len(items) < min_items:
            raise ValueError(f"Array at {path} does not meet minItems.")
        return items

    def _repair_object(self, value: Any, schema: dict[str, Any], path: str) -> JSONReturnType:
        if (
            self.schema_repair_mode == "salvage"
            and isinstance(value, list)
            and self._can_salvage_list_as_object(schema)
        ):
            mapped = self._map_list_to_object(value, schema, path)
            if mapped is not None:
                value = mapped
            elif path == "$" and len(value) == 1 and isinstance(value[0], dict):
                # Conservatively unwrap the common root wrapper shape: [{...}] -> {...}.
                value = value[0]
                self._log("Unwrapped single-item root array to object while salvaging", path)
        if not isinstance(value, dict):
            raise ValueError(f"Expected object at {path}, got {type(value).__name__}.")

        schema_config = object_schema_config(schema)

        if self.schema_repair_mode == "salvage" and schema_config.required:
            value_with_salvage_fills = dict(value)
            for key in schema_config.required:
                if key in value_with_salvage_fills:
                    continue
                prop_schema = schema_config.properties.get(key)
                if prop_schema is None:
                    continue
                key_path = f"{path}.{key}"
                filled, filled_value = self._fill_missing_required_for_salvage(prop_schema, key_path)
                if filled:
                    value_with_salvage_fills[key] = filled_value
                    self._log("Filled missing required property while salvaging", key_path)
            value = value_with_salvage_fills

        missing_required = [key for key in schema_config.required if key not in value]
        if missing_required:
            raise ValueError(f"Missing required properties at {path}: {', '.join(missing_required)}")

        repaired: dict[str, JSONReturnType] = {}

        for key, prop_schema in schema_config.properties.items():
            key_path = f"{path}.{key}"
            if key in value:
                repaired[key] = self.repair_value(value[key], prop_schema, key_path)
            elif isinstance(prop_schema, dict) and "default" in prop_schema and key not in schema_config.required:
                repaired[key] = self._copy_json_value(prop_schema["default"], key_path, "default")
                self._log("Inserted default value for missing property", key_path)

        for key, raw_value in value.items():
            if key in schema_config.properties:
                continue
            key_path = f"{path}.{key}"
            matched: list[Any] = []
            unsupported_patterns: list[str] = []
            if schema_config.pattern_properties:
                matched, unsupported_patterns = match_pattern_properties(schema_config.pattern_properties, key)
            for pattern in unsupported_patterns:
                self._log(f"Skipped unsupported patternProperties regex '{pattern}'", key_path)
            if matched:
                repaired_value = self.repair_value(raw_value, matched[0], key_path)
                for prop_schema in matched[1:]:
                    repaired_value = self.repair_value(repaired_value, prop_schema, key_path)
                repaired[key] = repaired_value
                continue
            if isinstance(schema_config.additional_properties, dict):
                repaired[key] = self.repair_value(
                    raw_value,
                    cast("dict[str, Any]", schema_config.additional_properties),
                    key_path,
                )
                continue
            if schema_config.additional_properties is True or schema_config.additional_properties is None:
                repaired[key] = normalize_missing_values(raw_value)
                continue
            self._log("Dropped extra property not covered by schema", key_path)

        min_properties = schema.get("minProperties")
        if min_properties is not None and len(repaired) < min_properties:
            raise ValueError(f"Object at {path} does not meet minProperties.")
        return repaired

    def _map_list_to_object(
        self, value: list[Any], schema: dict[str, Any], path: str
    ) -> dict[str, JSONReturnType] | None:
        properties = schema.get("properties")
        if not isinstance(properties, dict) or not properties:
            return None

        typed_properties: dict[str, Any] = {}
        for key, prop_schema in properties.items():
            if not isinstance(key, str):
                raise SchemaDefinitionError("Schema object property names must be strings.")
            typed_properties[key] = prop_schema

        keys = list(typed_properties.keys())
        if len(value) != len(keys):
            return None

        mapped: dict[str, JSONReturnType] = {}
        for idx, key in enumerate(keys):
            key_path = f"{path}.{key}"
            try:
                mapped[key] = self.repair_value(value[idx], typed_properties[key], key_path)
            except SchemaDefinitionError:
                raise
            except ValueError:
                return None

        self._log("Mapped array to object by schema property order", path)
        return mapped

    def _fill_missing_required_for_salvage(self, schema: object, path: str) -> tuple[bool, JSONReturnType]:
        resolved_schema = self.resolve_schema(schema)
        if not isinstance(resolved_schema, dict):
            return False, ""

        if "default" in resolved_schema:
            return True, self._copy_json_value(resolved_schema["default"], path, "default")
        if "const" in resolved_schema:
            return True, self._copy_json_value(resolved_schema["const"], path, "const")
        enum_values = resolved_schema.get("enum")
        if enum_values:
            return True, self._copy_json_value(enum_values[0], path, "enum")

        expected_type = resolved_schema.get("type")
        if expected_type is None:
            if self.is_array_schema(resolved_schema):
                expected_type = "array"
            elif self.is_object_schema(resolved_schema):
                expected_type = "object"

        if expected_type == "array" and not resolved_schema.get("minItems"):
            return True, []
        if expected_type == "object" and not resolved_schema.get("minProperties"):
            return True, {}

        return False, ""

    def _fill_missing(self, schema: dict[str, Any], path: str) -> JSONReturnType:
        if "const" in schema:
            # Const/enum/default have priority over type inference.
            self._log("Filled missing value with const", path)
            return self._copy_json_value(schema["const"], path, "const")
        if "enum" in schema:
            enum_values = schema["enum"]
            if not enum_values:
                raise ValueError(f"Enum at {path} has no values.")
            self._log("Filled missing value with first enum value", path)
            return self._copy_json_value(enum_values[0], path, "enum")
        if "default" in schema:
            self._log("Filled missing value with default", path)
            return self._copy_json_value(schema["default"], path, "default")

        expected_type = schema.get("type")
        if isinstance(expected_type, list):
            for schema_type in expected_type:
                try:
                    return self._fill_missing({**schema, "type": schema_type}, path)
                except ValueError:
                    continue
            raise ValueError(f"Cannot infer missing value at {path}.")

        if expected_type is None:
            # Infer container types based on schema shape if type is omitted.
            if self.is_object_schema(schema):
                expected_type = "object"
            elif self.is_array_schema(schema):
                expected_type = "array"

        if expected_type == "string":
            self._log("Filled missing value with empty string", path)
            return ""
        if expected_type in ("integer", "number"):
            self._log("Filled missing value with 0", path)
            return 0
        if expected_type == "boolean":
            self._log("Filled missing value with false", path)
            return False
        if expected_type == "array":
            min_items = schema.get("minItems")
            if min_items:
                raise ValueError(f"Array at {path} requires at least {min_items} items.")
            self._log("Filled missing value with empty array", path)
            return []
        if expected_type == "object":
            min_properties = schema.get("minProperties")
            if min_properties:
                raise ValueError(f"Object at {path} requires at least {min_properties} properties.")
            self._log("Filled missing value with empty object", path)
            return {}
        if expected_type == "null":
            self._log("Filled missing value with null", path)
            return None

        raise ValueError(f"Cannot infer missing value at {path}.")

    def _coerce_scalar(self, value: Any, schema_type: str, path: str) -> JSONReturnType:
        if schema_type == "string":
            if isinstance(value, str):
                return value
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                self._log("Coerced number to string", path)
                return str(value)
            raise ValueError(f"Expected string at {path}.")

        if schema_type == "integer":
            if isinstance(value, bool):
                raise ValueError(f"Expected integer at {path}.")
            if isinstance(value, int):
                return value
            if isinstance(value, float):
                if value.is_integer():
                    self._log("Coerced number to integer", path)
                    return int(value)
                raise ValueError(f"Expected integer at {path}.")
            if isinstance(value, str):
                try:
                    int_value = int(value)
                except ValueError:
                    int_value = None
                if int_value is not None:
                    self._log("Coerced string to integer", path)
                    return int_value
                try:
                    num = float(value)
                except ValueError as exc:
                    raise ValueError(f"Expected integer at {path}.") from exc
                if not num.is_integer():
                    raise ValueError(f"Expected integer at {path}.")
                self._log("Coerced number to integer", path)
                return int(num)
            raise ValueError(f"Expected integer at {path}.")

        if schema_type == "number":
            if isinstance(value, bool):
                raise ValueError(f"Expected number at {path}.")
            if isinstance(value, (int, float)):
                return value
            if isinstance(value, str):
                try:
                    float_value = float(value)
                except ValueError as exc:
                    raise ValueError(f"Expected number at {path}.") from exc
                self._log("Coerced string to number", path)
                return float_value
            raise ValueError(f"Expected number at {path}.")

        if schema_type == "boolean":
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                lowered = value.lower()
                if lowered in ("true", "yes", "y", "on", "1"):
                    self._log("Coerced string to boolean", path)
                    return True
                if lowered in ("false", "no", "n", "off", "0"):
                    self._log("Coerced string to boolean", path)
                    return False
            if isinstance(value, (int, float)) and not isinstance(value, bool) and value in (0, 1):
                self._log("Coerced number to boolean", path)
                return bool(value)
            raise ValueError(f"Expected boolean at {path}.")

        if schema_type == "null":
            if value is None:
                return None
            raise ValueError(f"Expected null at {path}.")

        raise SchemaDefinitionError(f"Unsupported schema type {schema_type} at {path}.")

    def _apply_enum_const(self, value: JSONReturnType, schema: dict[str, Any], path: str) -> JSONReturnType:
        if "const" in schema and value != schema["const"]:
            raise ValueError(f"Value at {path} does not match const.")
        if "enum" in schema and value not in schema["enum"]:
            raise ValueError(f"Value at {path} does not match enum.")
        return value

    def _resolve_ref(self, ref: str) -> dict[str, Any] | bool:
        if not ref.startswith("#/"):
            raise SchemaDefinitionError(f"Unsupported $ref: {ref}")
        parts = ref.lstrip("#/").split("/")
        current: Any = self.root_schema
        for part in parts:
            resolved_part = part.replace("~1", "/").replace("~0", "~")
            if not isinstance(current, dict) or resolved_part not in current:
                raise SchemaDefinitionError(f"Unresolvable $ref: {ref}")
            current = current[resolved_part]
        if isinstance(current, dict):
            return current
        if current is True:
            return True
        if current is False:
            return False
        raise SchemaDefinitionError(f"Unresolvable $ref: {ref}")

    def _copy_json_value(self, value: Any, path: str, label: str) -> JSONReturnType:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, list):
            return [self._copy_json_value(item, f"{path}[{idx}]", label) for idx, item in enumerate(value)]
        if isinstance(value, dict):
            copied: dict[str, JSONReturnType] = {}
            for key, item in value.items():
                if not isinstance(key, str):
                    raise ValueError(f"{label.capitalize()} value at {path} contains a non-string key.")
                copied[key] = self._copy_json_value(item, f"{path}.{key}", label)
            return copied
        raise ValueError(f"{label.capitalize()} value at {path} is not JSON compatible.")

    def _prepare_schema_for_validation(self, schema: object) -> dict[str, Any]:
        normalized = _prepare_schema_for_validation_node(schema)
        if not isinstance(normalized, dict):
            raise ValueError("Schema must be an object.")
        return normalized
