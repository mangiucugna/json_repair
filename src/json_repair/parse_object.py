from typing import TYPE_CHECKING, Any, cast

from .parser_schema import ObjectSchemaConfig, resolve_parser_object_schema
from .utils.constants import MISSING_VALUE, STRING_DELIMITERS, JSONReturnType
from .utils.json_context import ContextValues
from .utils.pattern_properties import match_pattern_properties

if TYPE_CHECKING:
    from .json_parser import JSONParser
    from .schema_repair import SchemaRepairer


def _finalize_object(
    obj: dict[str, JSONReturnType],
    schema_repairer: "SchemaRepairer | None",
    schema_config: ObjectSchemaConfig | None,
    path: str,
) -> dict[str, JSONReturnType]:
    if schema_repairer is None or schema_config is None:
        return obj

    missing_required = [key for key in schema_config.required if key not in obj]
    if missing_required and schema_repairer.schema_repair_mode != "salvage":
        raise ValueError(f"Missing required properties at {path}: {', '.join(missing_required)}")

    for key, prop_schema in schema_config.properties.items():
        if key in obj or key in schema_config.required:
            continue
        if isinstance(prop_schema, dict) and "default" in prop_schema:
            obj[key] = schema_repairer._copy_json_value(prop_schema["default"], f"{path}.{key}", "default")
            schema_repairer._log("Inserted default value for missing property", f"{path}.{key}")
    return obj


def _classify_empty_object_repair(
    self: "JSONParser",
    start_index: int,
    schema: dict[str, Any] | bool | None,
    schema_repairer: "SchemaRepairer | None",
) -> tuple[str, str | None]:
    attempted_object = self.json_str[start_index - 1 : self.index + 1]
    body = attempted_object[1:]
    body = body.removesuffix("}")
    body = body.lstrip()
    if not body:
        return "keep", None
    if (body.startswith('\\"') and '\\":' in body) or (body.startswith("\\'") and "\\':" in body):
        normalized_object = attempted_object.replace('\\"', '"').replace("\\'", "'")
        self.log(
            "Parsed object is empty but the input starts like an escaped object key, normalizing and reparsing it as an object",
        )
        return "object", normalized_object

    in_quote: str | None = None
    backslashes = 0
    for char in body:
        if char == "\\":
            backslashes += 1
            continue
        if in_quote is not None:
            if char == in_quote and backslashes % 2 == 0:
                in_quote = None
        elif char in STRING_DELIMITERS and backslashes % 2 == 0:
            in_quote = char
        elif char == ":" and backslashes % 2 == 0:
            self.log(
                "Parsed object is empty but the input still contains an object-style separator, keeping object repair",
            )
            return "keep", None
        backslashes = 0
    if (
        schema_repairer is not None
        and schema_repairer.schema_repair_mode == "salvage"
        and isinstance(schema, dict)
        and schema_repairer.is_object_schema(schema)
        and not schema_repairer.is_array_schema(schema)
    ):
        return "schema_set_object", None
    return "array", None


def _merge_object_array_continuation(
    self: "JSONParser",
    obj: dict[str, JSONReturnType],
) -> bool:
    prev_key = list(obj.keys())[-1] if obj else None
    if not prev_key or not isinstance(obj[prev_key], list) or self.strict:
        return False

    self.index += 1
    new_array = self.parse_array()
    if isinstance(new_array, list):
        prev_value = obj[prev_key]
        if isinstance(prev_value, list):
            list_lengths = [len(item) for item in prev_value if isinstance(item, list)]
            expected_len = (
                list_lengths[0] if list_lengths and all(length == list_lengths[0] for length in list_lengths) else None
            )
            if expected_len:
                tail = []
                while prev_value and not isinstance(prev_value[-1], list):
                    tail.append(prev_value.pop())
                if tail:
                    tail.reverse()
                    if len(tail) % expected_len == 0:
                        self.log(
                            "While parsing an object we found row values without an inner array, grouping them into rows",
                        )
                        for i in range(0, len(tail), expected_len):
                            prev_value.append(tail[i : i + expected_len])
                    else:
                        prev_value.extend(tail)
                if new_array:
                    if all(isinstance(item, list) for item in new_array):
                        self.log(
                            "While parsing an object we found additional rows, appending them without flattening",
                        )
                        prev_value.extend(new_array)
                    else:
                        prev_value.append(new_array)
            else:
                prev_value.extend(new_array[0] if len(new_array) == 1 and isinstance(new_array[0], list) else new_array)

    self.skip_whitespaces()
    if self.get_char_at() == ",":
        self.index += 1
    self.skip_whitespaces()
    return True


def _parse_object_key(
    self: "JSONParser",
    obj: dict[str, JSONReturnType],
) -> tuple[str, int]:
    key = ""
    rollback_index = self.index
    with self.context.enter(ContextValues.OBJECT_KEY):
        while self.get_char_at():
            rollback_index = self.index
            if self.get_char_at() == "[" and key == "" and _merge_object_array_continuation(self, obj):
                continue

            raw_key = self.parse_string()
            assert isinstance(raw_key, str)
            key = raw_key
            if key == "":
                self.skip_whitespaces()
            if key != "" or (key == "" and self.get_char_at() in [":", "}"]):
                if key == "" and self.strict:
                    self.log(
                        "Empty key found in strict mode while parsing object, raising an error",
                    )
                    raise ValueError("Empty key found in strict mode while parsing object.")
                break
    return key, rollback_index


def _should_split_duplicate_object(self: "JSONParser", rollback_index: int) -> bool:
    lookback_idx = rollback_index - self.index - 1
    prev_non_whitespace = self.get_char_at(lookback_idx)
    while prev_non_whitespace and prev_non_whitespace.isspace():
        lookback_idx -= 1
        prev_non_whitespace = self.get_char_at(lookback_idx)
    key_start_char = self.get_char_at(rollback_index - self.index)
    next_non_whitespace = self.get_char_at(self.scroll_whitespaces())
    return not (key_start_char in STRING_DELIMITERS and prev_non_whitespace == "," and next_non_whitespace == ":")


def _split_object_on_duplicate_key(self: "JSONParser", rollback_index: int) -> None:
    self.index = rollback_index - 1
    self.json_str = self.json_str[: self.index + 1] + "{" + self.json_str[self.index + 1 :]


def _resolve_object_property_schema(
    self: "JSONParser",
    schema_repairer: "SchemaRepairer | None",
    schema_config: ObjectSchemaConfig | None,
    key: str,
) -> tuple[dict[str, Any] | bool | None, list[dict[str, Any] | bool | None], bool]:
    if schema_repairer is None or schema_config is None:
        return None, [], False

    prop_schema: dict[str, Any] | bool | None = None
    extra_schemas: list[dict[str, Any] | bool | None] = []
    if key in schema_config.properties:
        schema_value = schema_config.properties[key]
        if schema_value is not None and not isinstance(schema_value, (dict, bool)):
            raise ValueError("Schema must be an object.")
        prop_schema = cast("dict[str, Any] | bool | None", schema_value)
        return prop_schema, extra_schemas, False

    matched: list[Any] = []
    unsupported_patterns: list[str] = []
    if schema_config.pattern_properties:
        matched, unsupported_patterns = match_pattern_properties(schema_config.pattern_properties, key)
    for pattern in unsupported_patterns:
        self.log(
            f"Skipped unsupported patternProperties regex '{pattern}' while parsing object key '{key}'",
        )
    if matched:
        primary_schema = matched[0]
        if primary_schema is not None and not isinstance(primary_schema, (dict, bool)):
            raise ValueError("Schema must be an object.")
        prop_schema = cast("dict[str, Any] | bool | None", primary_schema)
        for extra_schema in matched[1:]:
            if extra_schema is not None and not isinstance(extra_schema, (dict, bool)):
                raise ValueError("Schema must be an object.")
            extra_schemas.append(cast("dict[str, Any] | bool | None", extra_schema))
        return prop_schema, extra_schemas, False

    if schema_config.additional_properties is False:
        return None, [], True
    if isinstance(schema_config.additional_properties, dict):
        return cast("dict[str, Any]", schema_config.additional_properties), [], False
    return True, [], False


def _parse_object_value(
    self: "JSONParser",
    schema_repairer: "SchemaRepairer | None",
    prop_schema: dict[str, Any] | bool | None,
    key_path: str,
) -> JSONReturnType:
    with self.context.enter(ContextValues.OBJECT_VALUE):
        self.skip_whitespaces()
        char = self.get_char_at()
        if char in [",", "}"]:
            self.log(
                f"While parsing an object value we found a stray {char}, ignoring it",
            )
            if schema_repairer is not None:
                return schema_repairer.repair_value(MISSING_VALUE, prop_schema, key_path)
            return ""

        if schema_repairer is not None:
            return self.parse_json(prop_schema, key_path)
        return self.parse_json()


def _repair_empty_object_result(
    self: "JSONParser",
    obj: dict[str, JSONReturnType],
    start_index: int,
    schema: dict[str, Any] | bool | None,
    path: str,
    schema_repairer: "SchemaRepairer | None",
) -> tuple[bool, JSONReturnType]:
    if obj or self.index - start_index <= 2:
        return False, None

    if self.strict:
        self.log(
            "Parsed object is empty but contains extra characters in strict mode, raising an error",
        )
        raise ValueError("Parsed object is empty but contains extra characters in strict mode.")

    empty_object_repair, normalized_object = _classify_empty_object_repair(self, start_index, schema, schema_repairer)
    if empty_object_repair == "object" and normalized_object is not None:
        end_index = self.index + 1
        self.json_str = self.json_str[: start_index - 1] + normalized_object + self.json_str[end_index:]
        self.index = start_index
        with self.context.enter(ContextValues.OBJECT_KEY):
            repaired_value = self.parse_object(schema, path)
        self.deferred_contexts.append(ContextValues.OBJECT_KEY)
        return True, repaired_value
    if empty_object_repair == "schema_set_object":
        self.log(
            "Parsed object is empty but salvage schema expects an object, reparsing set-like members as null-valued object keys",
        )
        self.index = start_index
        with self.context.enter(ContextValues.OBJECT_KEY):
            set_items = self.parse_array()
        self.deferred_contexts.append(ContextValues.OBJECT_KEY)
        if isinstance(set_items, list):
            key_candidates: list[str] = [item for item in set_items if isinstance(item, str) and item]
            if len(key_candidates) == len(set_items):
                return True, cast("JSONReturnType", dict.fromkeys(key_candidates))
        return True, set_items
    if empty_object_repair == "array":
        self.log("Parsed object is empty, we will try to parse this as an array instead")
        self.index = start_index
        with self.context.enter(ContextValues.OBJECT_KEY):
            repaired_array = self.parse_array()
        self.deferred_contexts.append(ContextValues.OBJECT_KEY)
        return True, repaired_array
    return False, None


def _complete_object_parse(
    self: "JSONParser",
    obj: dict[str, JSONReturnType],
    schema: dict[str, Any] | bool | None,
    path: str,
    schema_repairer: "SchemaRepairer | None",
    schema_config: ObjectSchemaConfig | None,
) -> JSONReturnType:
    if not self.context.empty:
        if self.get_char_at() == "}" and self.context.current not in [
            ContextValues.OBJECT_KEY,
            ContextValues.OBJECT_VALUE,
        ]:
            self.log(
                "Found an extra closing brace that shouldn't be there, skipping it",
            )
            self.index += 1
        return obj

    self.skip_whitespaces()
    if self.get_char_at() == ",":
        self.index += 1
        self.skip_whitespaces()
        if self.get_char_at() in STRING_DELIMITERS and not self.strict:
            self.log(
                "Found a comma and string delimiter after object closing brace, checking for additional key-value pairs",
            )
            additional_obj = self.parse_object(schema, path)
            if isinstance(additional_obj, dict):
                obj.update(additional_obj)

    return _finalize_object(obj, schema_repairer, schema_config, path)


def parse_object(
    self: "JSONParser",
    schema: dict[str, Any] | bool | None = None,
    path: str = "$",
) -> JSONReturnType:
    # <object> ::= '{' [ <member> *(', ' <member>) ] '}' ; A sequence of 'members'
    obj: dict[str, JSONReturnType] = {}
    start_index = self.index
    parsing_object_value = self.context.current == ContextValues.OBJECT_VALUE
    schema_repairer, schema, schema_config = resolve_parser_object_schema(self.schema_repairer, schema)

    while (self.get_char_at() or "}") != "}":
        self.skip_whitespaces()

        if self.get_char_at() == ":":
            self.log(
                "While parsing an object we found a : before a key, ignoring",
            )
            self.index += 1

        key, rollback_index = _parse_object_key(self, obj)
        if ContextValues.ARRAY in self.context.context and key in obj:
            if self.strict:
                self.log("Duplicate key found in strict mode while parsing object, raising an error")
                raise ValueError("Duplicate key found in strict mode while parsing object.")
            if not parsing_object_value:
                if _should_split_duplicate_object(self, rollback_index):
                    self.log(
                        "While parsing an object we found a duplicate key, closing the object here and rolling back the index",
                    )
                    _split_object_on_duplicate_key(self, rollback_index)
                    break
                self.log(
                    "While parsing an object we found a duplicate key with a normal comma separator, keeping duplicate-key overwrite behavior",
                )

        self.skip_whitespaces()
        if (self.get_char_at() or "}") == "}":
            continue

        self.skip_whitespaces()
        if self.get_char_at() != ":":
            if self.strict:
                self.log(
                    "Missing ':' after key in strict mode while parsing object, raising an error",
                )
                raise ValueError("Missing ':' after key in strict mode while parsing object.")
            self.log(
                "While parsing an object we missed a : after a key",
            )

        self.index += 1
        prop_schema, extra_schemas, drop_property = _resolve_object_property_schema(
            self,
            schema_repairer,
            schema_config,
            key,
        )
        key_path = f"{path}.{key}"
        value = _parse_object_value(self, schema_repairer, prop_schema, key_path)

        if schema_repairer is not None:
            for extra_schema in extra_schemas:
                value = schema_repairer.repair_value(value, extra_schema, key_path)

        if schema_repairer is None and value == "" and self.strict and self.get_char_at(-1) not in STRING_DELIMITERS:
            self.log(
                "Parsed value is empty in strict mode while parsing object, raising an error",
            )
            raise ValueError("Parsed value is empty in strict mode while parsing object.")

        if schema_repairer is None or not drop_property:
            obj[key] = value
        else:
            schema_repairer._log("Dropped extra property not covered by schema", key_path)

        if self.get_char_at() in [",", "'", '"']:
            self.index += 1
        if self.get_char_at() == "]" and ContextValues.ARRAY in self.context.context:
            self.log(
                "While parsing an object we found a closing array bracket, closing the object here and rolling back the index"
            )
            self.index -= 1
            break
        self.skip_whitespaces()

    self.index += 1

    repaired_empty_object, repaired_value = _repair_empty_object_result(
        self,
        obj,
        start_index,
        schema,
        path,
        schema_repairer,
    )
    if repaired_empty_object:
        return repaired_value

    return _complete_object_parse(
        self,
        obj,
        schema,
        path,
        schema_repairer,
        schema_config,
    )
