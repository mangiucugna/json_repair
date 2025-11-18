from typing import TYPE_CHECKING

from .utils.constants import STRING_DELIMITERS, JSONReturnType
from .utils.json_context import ContextValues

if TYPE_CHECKING:
    from .json_parser import JSONParser


def parse_object(self: "JSONParser") -> JSONReturnType:
    # <object> ::= '{' [ <member> *(', ' <member>) ] '}' ; A sequence of 'members'
    obj: dict[str, JSONReturnType] = {}
    start_index = self.index
    # Stop when you either find the closing parentheses or you have iterated over the entire string
    while (self.get_char_at() or "}") != "}":
        # This is what we expect to find:
        # <member> ::= <string> ': ' <json>

        # Skip filler whitespaces
        self.skip_whitespaces()

        # Sometimes LLMs do weird things, if we find a ":" so early, we'll change it to "," and move on
        if self.get_char_at() == ":":
            self.log(
                "While parsing an object we found a : before a key, ignoring",
            )
            self.index += 1

        # We are now searching for they string key
        # Context is used in the string parser to manage the lack of quotes
        self.context.set(ContextValues.OBJECT_KEY)

        # Save this index in case we need find a duplicate key
        rollback_index = self.index

        # <member> starts with a <string>
        key = ""
        while self.get_char_at():
            # The rollback index needs to be updated here in case the key is empty
            rollback_index = self.index
            if self.get_char_at() == "[" and key == "":
                # Is this an array?
                # Need to check if the previous parsed value contained in obj is an array and in that case parse and merge the two
                prev_key = list(obj.keys())[-1] if obj else None
                if prev_key and isinstance(obj[prev_key], list):
                    # If the previous key's value is an array, parse the new array and merge
                    self.index += 1
                    new_array = self.parse_array()
                    if isinstance(new_array, list):
                        # Merge and flatten the arrays
                        prev_value = obj[prev_key]
                        if isinstance(prev_value, list):
                            prev_value.extend(
                                new_array[0] if len(new_array) == 1 and isinstance(new_array[0], list) else new_array
                            )
                        self.skip_whitespaces()
                        if self.get_char_at() == ",":
                            self.index += 1
                        self.skip_whitespaces()
                        continue
            key = str(self.parse_string())
            if key == "":
                self.skip_whitespaces()
            if key != "" or (key == "" and self.get_char_at() in [":", "}"]):
                # Empty keys now trigger in strict mode, otherwise we keep repairing as before
                if key == "" and self.strict:
                    self.log(
                        "Empty key found in strict mode while parsing object, raising an error",
                    )
                    raise ValueError("Empty key found in strict mode while parsing object.")
                break
        if ContextValues.ARRAY in self.context.context and key in obj:
            if self.strict:
                self.log("Duplicate key found in strict mode while parsing object, raising an error")
                raise ValueError("Duplicate key found in strict mode while parsing object.")
            self.log(
                "While parsing an object we found a duplicate key, closing the object here and rolling back the index",
            )
            self.index = rollback_index - 1
            # add an opening curly brace to make this work
            self.json_str = self.json_str[: self.index + 1] + "{" + self.json_str[self.index + 1 :]
            break

        # Skip filler whitespaces
        self.skip_whitespaces()

        # We reached the end here
        if (self.get_char_at() or "}") == "}":
            continue

        self.skip_whitespaces()

        # An extreme case of missing ":" after a key
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
        self.context.reset()
        self.context.set(ContextValues.OBJECT_VALUE)
        # The value can be any valid json; strict mode will refuse repaired empties
        self.skip_whitespaces()
        # Corner case, a lone comma
        value: JSONReturnType = ""
        if self.get_char_at() in [",", "}"]:
            self.log(
                "While parsing an object value we found a stray " + str(self.get_char_at()) + ", ignoring it",
            )
        else:
            value = self.parse_json()
        if value == "" and self.strict and self.get_char_at(-1) not in STRING_DELIMITERS:
            self.log(
                "Parsed value is empty in strict mode while parsing object, raising an error",
            )
            raise ValueError("Parsed value is empty in strict mode while parsing object.")
        # Reset context since our job is done
        self.context.reset()
        obj[key] = value

        if self.get_char_at() in [",", "'", '"']:
            self.index += 1

        # Remove trailing spaces
        self.skip_whitespaces()

    self.index += 1

    # If the object is empty but also isn't just {}
    if not obj and self.index - start_index > 2:
        if self.strict:
            self.log(
                "Parsed object is empty but contains extra characters in strict mode, raising an error",
            )
            raise ValueError("Parsed object is empty but contains extra characters in strict mode.")
        self.log("Parsed object is empty, we will try to parse this as an array instead")
        self.index = start_index
        return self.parse_array()

    # Check if there are more key-value pairs after the closing brace
    # This handles cases like '{"key": "value"}, "key2": "value2"}'
    # But only if we're not in a nested context
    if not self.context.empty:
        return obj

    self.skip_whitespaces()
    if self.get_char_at() != ",":
        return obj
    self.index += 1
    self.skip_whitespaces()
    if self.get_char_at() not in STRING_DELIMITERS:
        return obj
    if not self.strict:
        self.log(
            "Found a comma and string delimiter after object closing brace, checking for additional key-value pairs",
        )
        additional_obj = self.parse_object()
        if isinstance(additional_obj, dict):
            obj.update(additional_obj)

    return obj
