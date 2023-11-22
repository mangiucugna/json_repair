"""
This module will parse the JSON file following the BNF definition:

    <json> ::= <primitive> | <container>

    <primitive> ::= <number> | <string> | <boolean>
    ; Where:
    ; <number> is a valid real number expressed in one of a number of given formats
    ; <string> is a string of valid characters enclosed in quotes
    ; <boolean> is one of the literal strings 'true', 'false', or 'null' (unquoted)

    <container> ::= <object> | <array>
    <array> ::= '[' [ <json> *(', ' <json>) ] ']' ; A sequence of JSON values separated by commas
    <object> ::= '{' [ <member> *(', ' <member>) ] '}' ; A sequence of 'members'
    <member> ::= <string> ': ' <json> ; A pair consisting of a name, and a JSON value

If something is wrong (a missing parantheses or quotes for example) it will use a few simple heuristics to fix the JSON string:
- Add the missing parentheses if the parser believes that the array or object should be closed
- Quote strings or add missing single quotes
- Adjust whitespaces and remove line breaks

All supported use cases are in the unit tests
"""

import json
import re
from typing import Any, Dict, List, Union


class JSONParser:
    def __init__(self, json_str: str) -> None:
        # The string to parse
        self.json_str = json_str
        # Index is our iterator that will keep track of which character we are looking at right now
        self.index = 0
        # This is used in the object member parsing to manage the special cases of missing quotes in key or value
        self.context = ""

    def parse(self) -> Union[Dict[str, Any], List[Any], str, float, int, bool, None]:
        return self.parse_json()

    def parse_json(
        self,
    ) -> Union[Dict[str, Any], List[Any], str, float, int, bool, None]:
        char = self.get_char_at()
        # False means that we are at the end of the string provided, is the base case for recursion
        if char is False:
            return ""
        # <object> starts with '{'
        elif char == "{":
            self.index += 1
            return self.parse_object()
        # <array> starts with '['
        elif char == "[":
            self.index += 1
            return self.parse_array()
        # there can be an edge case in which a key is empty and at the end of an object
        # like "key": }. We return an empty string here to close the object properly
        elif char == "}" and self.context == "object_value":
            return ""
        # <string> starts with '"'
        elif char == '"':
            return self.parse_string()
        # <number> starts with [0-9] or minus
        elif char.isdigit() or char == "-":
            return self.parse_number()
        # <boolean> could be (T)rue or (F)alse or (N)ull
        elif char == "t" or char == "f" or char == "n":
            return self.parse_boolean_or_null()
        # This might be a <string> that is missing the starting '"'
        elif char.isalpha():
            return self.parse_string()
        # Ignore whitespaces outside of strings
        elif char.isspace():
            self.index += 1
            self.skip_whitespaces_at()
            return self.parse_json()
        # If everything else fails, then we give up and return an exception
        else:
            raise ValueError("Invalid JSON format")

    def parse_object(self) -> Dict[str, Any]:
        # <object> ::= '{' [ <member> *(', ' <member>) ] '}' ; A sequence of 'members'
        obj = {}
        # Stop when you either find the closing parentheses or you have iterated over the entire string
        while self.get_char_at() and self.get_char_at() != "}":
            # This is what we expect to find:
            # <member> ::= <string> ': ' <json>

            # Skip filler whitespaces
            self.skip_whitespaces_at()

            # Sometimes LLMs do weird things, if we find a ":" so early, we'll change it to "," and move on
            if self.get_char_at() == ":":
                self.remove_char_at()
                self.insert_char_at(",")
                self.index += 1

            # We are now searching for they string key
            # Context is used in the string parser to manage the lack of quotes
            self.context = "object_key"

            # <member> starts with a <string>
            self.skip_whitespaces_at()
            key = self.parse_string()
            while self.get_char_at() and key == "":
                key = self.parse_string()

            # We reached the end here
            if key == "}":
                continue

            # Reset context
            self.context = ""
            # An extreme case of missing ":" after a key
            if self.get_char_at() and self.get_char_at() != ":":
                self.insert_char_at(":")
            self.index += 1
            self.context = "object_value"
            # The value can be any valid json
            value = self.parse_json()
            self.context = ""
            obj[key] = value

            if self.get_char_at() == ",":
                self.index += 1

            # Remove trailing spaces
            self.skip_whitespaces_at()

        # Especially at the end of an LLM generated json you might miss the last "}"
        if self.get_char_at() and self.get_char_at() != "}":
            self.insert_char_at("}")
        self.index += 1
        return obj

    def parse_array(self) -> List[Any]:
        # <array> ::= '[' [ <json> *(', ' <json>) ] ']' ; A sequence of JSON values separated by commas
        arr = []
        # Stop when you either find the closing parentheses or you have iterated over the entire string
        char = self.get_char_at()
        while char and char != "]":
            value = self.parse_json()
            arr.append(value)

            # skip over whitespace after a value but before closing ]
            char = self.get_char_at()
            while char and (char.isspace() or char == ","):
                self.index += 1
                char = self.get_char_at()

            # Update the loop variable, in case someone above changed the index
            char = self.get_char_at()

        # Especially at the end of an LLM generated json you might miss the last "]"
        if self.get_char_at() != "]":
            # Sometimes when you fix a missing "]" you'll have a trailing "," there that makes the JSON invalid
            if self.get_char_at() == ",":
                # Remove trailing "," before adding the "]"
                self.remove_char_at()
            self.insert_char_at("]")

        self.index += 1
        return arr

    def parse_string(self) -> str:
        # <string> is a string of valid characters enclosed in quotes
        # Somehow all weird cases in an invalid JSON happen to be resolved in this function, so be careful here
        # Flag to manage corner cases related to missing starting quote
        fixed_quotes = False
        # i.e. { name: "John" }
        if self.get_char_at() != '"':
            self.insert_char_at('"')
            fixed_quotes = True
        else:
            self.index += 1
        # Start position of the string
        start = self.index

        # Here things get a bit hairy because a string missing the final quote can also be a key or a value in an object
        # In that case we need to use the ":|,|}" characters as terminators of the string
        # So this will stop if:
        # * It finds a closing quote
        # * It iterated over the entire sequence
        # * If we are fixing missing quotes in an object, when it finds the special terminators
        char = self.get_char_at()
        while (
            char
            and char != '"'
            and (not fixed_quotes or self.context != "object_key" or char != ":")
            and (not fixed_quotes or self.context != "object_key" or not char.isspace())
            and (
                not fixed_quotes
                or self.context != "object_value"
                or (char != "," and char != "}")
            )
        ):
            self.index += 1
            char = self.get_char_at()

        # If the cycle stopped at a space we have some doubts on wheter this is a valid string, check one char ahead
        if (
            self.get_char_at()
            and fixed_quotes
            and self.context == "object_key"
            and self.get_char_at().isspace()
        ):
            # skip whitespaces
            self.skip_whitespaces_at()
            # This string is invalid if there's no valid termination afterwards

            if self.get_char_at() not in [":", ","]:
                return ""

        end = self.index
        if self.get_char_at() != '"':
            self.insert_char_at('"')
        # A fallout of the previous special case in the while loop, we need to update the index only if we had a closing quote
        if self.get_char_at() == '"':
            self.index += 1

        return self.json_str[start:end]

    def parse_number(self) -> Union[float, int]:
        # <number> is a valid real number expressed in one of a number of given formats
        number_str = ""
        char = self.get_char_at()
        while char and (char.isdigit() or char in "-.eE"):
            number_str += char
            self.index += 1
            char = self.get_char_at()
        if number_str:
            if "." in number_str or "e" in number_str or "E" in number_str:
                return float(number_str)
            else:
                return int(number_str)
        else:
            # This is a string then
            return self.parse_string()

    def parse_boolean_or_null(self) -> Union[bool, None]:
        # <boolean> is one of the literal strings 'true', 'false', or 'null' (unquoted)
        if self.json_str.startswith("true", self.index):
            self.index += 4
            return True
        elif self.json_str.startswith("false", self.index):
            self.index += 5
            return False
        elif self.json_str.startswith("null", self.index):
            self.index += 4
            return None
        else:
            # This is a string then
            return self.parse_string()

    def insert_char_at(self, char: str) -> None:
        self.json_str = self.json_str[: self.index] + char + self.json_str[self.index :]
        self.index += 1

    def get_char_at(self) -> Union[str, bool]:
        # Why not use something simpler? Because we might be out of bounds and doing this check all the time is annoying
        try:
            return self.json_str[self.index]
        except IndexError:
            return False

    def remove_char_at(self) -> None:
        self.json_str = self.json_str[: self.index] + self.json_str[self.index + 1 :]

    def skip_whitespaces_at(self) -> None:
        # Remove trailing spaces
        # I'd rather not do this BUT this method is called so many times that it makes sense to expand get_char_at
        # At least this is what the profiler said and I believe in our lord and savior the profiler
        try:
            char = self.json_str[self.index]
        except IndexError:
            return
        while char and char.isspace():
            self.index += 1
            try:
                char = self.json_str[self.index]
            except IndexError:
                return


def repair_json(
    json_str: str, return_objects: bool = False, skip_json_loads: bool = False
) -> Union[Dict[str, Any], List[Any], str, float, int, bool, None]:
    """
    Given a json formatted string, it will try to decode it and, if it fails, it will try to fix it.
    It will return the fixed string by default.
    When `return_objects=True` is passed, it will return the decoded data structure instead.
    """
    json_str = re.sub(r"^\s+", "", json_str)
    json_str = re.sub(r"\s+$", "", json_str)
    json_str = re.sub(r"/\*.*?\*/", "", json_str)
    parser = JSONParser(json_str)
    if skip_json_loads:
        parsed_json = parser.parse()
    else:
        try:
            parsed_json = json.loads(json_str)
        except json.JSONDecodeError:
            parsed_json = parser.parse()
    # It's useful to return the actual object instead of the json string, it allows this lib to be a replacement of the json library
    if return_objects:
        return parsed_json
    return json.dumps(parsed_json)


def loads(
    json_str: str,
) -> Union[Dict[str, Any], List[Any], str, float, int, bool, None]:
    """
    This function works like `json.loads()` except that it will fix your JSON in the process.
    It is a wrapper around the `repair_json()` function with `return_objects=True`.
    """
    return repair_json(json_str, True)
