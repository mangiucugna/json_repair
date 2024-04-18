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
from typing import Any, Dict, List, Union, TextIO


class JSONParser:
    def __init__(self, json_str: str) -> None:
        # The string to parse
        self.json_str = json_str
        # Index is our iterator that will keep track of which character we are looking at right now
        self.index = 0
        # This is used in the object member parsing to manage the special cases of missing quotes in key or value
        self.context = ""
        self.context_stack = []

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
        elif char == "'":
            return self.parse_string(string_quotes="'")
        elif char == "“":
            return self.parse_string(string_quotes=["“", "”"])
        # <number> starts with [0-9] or minus
        elif char.isdigit() or char == "-":
            return self.parse_number()
        # <boolean> could be (T)rue or (F)alse or (N)ull
        elif char.lower() in ["t", "f", "n"]:
            return self.parse_boolean_or_null()
        # This might be a <string> that is missing the starting '"'
        elif char.isalpha():
            return self.parse_string()
        # If everything else fails, we just ignore and move on
        else:
            self.index += 1
            return self.parse_json()

    def parse_object(self) -> Dict[str, Any]:
        # <object> ::= '{' [ <member> *(', ' <member>) ] '}' ; A sequence of 'members'
        obj = {}
        # Stop when you either find the closing parentheses or you have iterated over the entire string
        while (self.get_char_at() or "}") != "}":
            # This is what we expect to find:
            # <member> ::= <string> ': ' <json>

            # Skip filler whitespaces
            self.skip_whitespaces_at()

            # Sometimes LLMs do weird things, if we find a ":" so early, we'll change it to "," and move on
            if (self.get_char_at() or "") == ":":
                self.remove_char_at()
                self.insert_char_at(",")
                self.index += 1

            # We are now searching for they string key
            # Context is used in the string parser to manage the lack of quotes
            self.update_context("object_key")

            self.skip_whitespaces_at()

            # <member> starts with a <string>
            key = ""
            while key == "" and self.get_char_at():
                key = self.parse_json()

                # This can happen sometimes like { "": "value" }
                if key == "" and self.get_char_at() == ":":
                    key = "empty_placeholder"
                    break

            # We reached the end here
            if (self.get_char_at() or "}") == "}":
                continue

            # An extreme case of missing ":" after a key
            if (self.get_char_at() or "") != ":":
                self.insert_char_at(":")
            self.index += 1
            self.update_context("")
            self.update_context("object_value")
            # The value can be any valid json
            value = self.parse_json()

            # Reset context since our job is done
            self.update_context("")
            obj[key] = value

            if (self.get_char_at() or "") in [",", "'", '"']:
                self.index += 1

            # Remove trailing spaces
            self.skip_whitespaces_at()

        # Especially at the end of an LLM generated json you might miss the last "}"
        if (self.get_char_at() or "}") != "}":
            self.insert_char_at("}")
        self.index += 1
        return obj

    def parse_array(self) -> List[Any]:
        # <array> ::= '[' [ <json> *(', ' <json>) ] ']' ; A sequence of JSON values separated by commas
        arr = []
        # Stop when you either find the closing parentheses or you have iterated over the entire string
        while (self.get_char_at() or "]") != "]":
            value = self.parse_json()

            # It is possible that parse_json() returns nothing valid, so we stop
            if not value:
                break

            arr.append(value)

            # skip over whitespace after a value but before closing ]
            char = self.get_char_at()
            while char and (char.isspace() or char == ","):
                self.index += 1
                char = self.get_char_at()
            # If this is the right value of an object and we are closing the object, it means the array is over
            if self.context == "object_value" and char == "}":
                break

        # Especially at the end of an LLM generated json you might miss the last "]"
        char = self.get_char_at()
        if char and char != "]":
            # Sometimes when you fix a missing "]" you'll have a trailing "," there that makes the JSON invalid
            if char == ",":
                # Remove trailing "," before adding the "]"
                self.remove_char_at()
            self.insert_char_at("]")
            self.index -= 1

        self.index += 1
        return arr

    def parse_string(self, string_quotes=False) -> str:
        # <string> is a string of valid characters enclosed in quotes
        # i.e. { name: "John" }
        # Somehow all weird cases in an invalid JSON happen to be resolved in this function, so be careful here

        # Flag to manage corner cases related to missing starting quote
        fixed_quotes = False
        double_delimiter = False
        lstring_delimiter = rstring_delimiter = '"'
        if isinstance(string_quotes, list):
            lstring_delimiter = string_quotes[0]
            rstring_delimiter = string_quotes[1]
        elif isinstance(string_quotes, str):
            lstring_delimiter = rstring_delimiter = string_quotes
        if self.get_char_at(1) == lstring_delimiter:
            double_delimiter = True
            self.index += 1
        char = self.get_char_at()
        if char != lstring_delimiter:
            self.insert_char_at(lstring_delimiter)
            fixed_quotes = True
        else:
            self.index += 1

        # Start position of the string (to use later in the return value)
        start = self.index

        # Here things get a bit hairy because a string missing the final quote can also be a key or a value in an object
        # In that case we need to use the ":|,|}" characters as terminators of the string
        # So this will stop if:
        # * It finds a closing quote
        # * It iterated over the entire sequence
        # * If we are fixing missing quotes in an object, when it finds the special terminators
        char = self.get_char_at()
        fix_broken_markdown_link = False
        while char and char != rstring_delimiter:
            if fixed_quotes:
                if self.context == "object_key" and (char == ":" or char.isspace()):
                    break
                elif self.context == "object_value" and char in [",", "}"]:
                    break
            self.index += 1
            char = self.get_char_at()
            # If the string contains an escaped character we should respect that or remove the escape
            if self.get_char_at(-1) == "\\":
                if char in [rstring_delimiter, "t", "n", "r", "b", "\\"]:
                    self.index += 1
                    char = self.get_char_at()
                else:
                    self.remove_char_at(-1)
                    self.index -= 1
            # ChatGPT sometimes forget to quote links in markdown like: { "content": "[LINK]("https://google.com")" }
            if (
                char == rstring_delimiter
                # Next character is not a comma
                and self.get_char_at(1) != ","
                and (
                    fix_broken_markdown_link
                    or (self.get_char_at(-2) == "]" and self.get_char_at(-1)) == "("
                )
            ):
                fix_broken_markdown_link = not fix_broken_markdown_link
                self.index += 1
                char = self.get_char_at()

        if char and fixed_quotes and self.context == "object_key" and char.isspace():
            self.skip_whitespaces_at()
            if self.get_char_at() not in [":", ","]:
                return ""

        end = self.index

        # A fallout of the previous special case in the while loop, we need to update the index only if we had a closing quote
        if char != rstring_delimiter:
            self.insert_char_at(rstring_delimiter)
        else:
            self.index += 1
            if double_delimiter and self.get_char_at() == rstring_delimiter:
                self.index += 1

        return self.json_str[start:end]

    def parse_number(self) -> Union[float, int, str]:
        # <number> is a valid real number expressed in one of a number of given formats
        number_str = ""
        number_chars = set("0123456789-.eE")
        char = self.get_char_at()
        while char and char in number_chars:
            number_str += char
            self.index += 1
            char = self.get_char_at()
        if number_str:
            try:
                if "." in number_str or "e" in number_str or "E" in number_str:
                    return float(number_str)
                elif number_str == "-":
                    # If there is a stray "-" this will throw an exception, throw away this character
                    return self.parse_json()
                else:
                    return int(number_str)
            except ValueError:
                return number_str
        else:
            # This is a string then
            return self.parse_string()

    def parse_boolean_or_null(self) -> Union[bool, str, None]:
        # <boolean> is one of the literal strings 'true', 'false', or 'null' (unquoted)
        boolean_map = {"true": (True, 4), "false": (False, 5), "null": (None, 4)}
        for key, (value, length) in boolean_map.items():
            if self.json_str.lower().startswith(key, self.index):
                self.index += length
                return value

        # This is a string then
        return self.parse_string()

    def insert_char_at(self, char: str) -> None:
        self.json_str = self.json_str[: self.index] + char + self.json_str[self.index :]
        self.index += 1

    def get_char_at(self, count: int = 0) -> Union[str, bool]:
        # Why not use something simpler? Because we might be out of bounds and doing this check all the time is annoying
        try:
            return self.json_str[self.index + count]
        except IndexError:
            return False

    def remove_char_at(self, count: int = 0) -> None:
        self.json_str = (
            self.json_str[: self.index + count]
            + self.json_str[self.index + count + 1 :]
        )

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

    def update_context(self, value: str) -> None:
        # If a value is provided update the context variable and save in stack
        if value:
            if self.context:
                self.context_stack.append(self.context)
            self.context = value
        # Otherwise pop and update the context, or empty if the stack is empty
        else:
            try:
                self.context = self.context_stack.pop()
            except Exception:
                self.context = ""


def repair_json(
    json_str: str, return_objects: bool = False, skip_json_loads: bool = False
) -> Union[Dict[str, Any], List[Any], str, float, int, bool, None]:
    """
    Given a json formatted string, it will try to decode it and, if it fails, it will try to fix it.
    It will return the fixed string by default.
    When `return_objects=True` is passed, it will return the decoded data structure instead.
    """
    json_str = json_str.strip().lstrip("```json")
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


def load(fp: TextIO) -> Union[Dict[str, Any], List[Any], str, float, int, bool, None]:
    return loads(fp.read())


def from_file(
    filename: str,
) -> Union[Dict[str, Any], List[Any], str, float, int, bool, None]:
    fd = open(filename)
    jsonobj = load(fd)
    fd.close()

    return jsonobj
