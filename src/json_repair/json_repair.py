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
    def __init__(self, json_str: str, json_fd: TextIO, logging: bool = False) -> None:
        # The string to parse
        self.json_str = json_str
        # Alternatively, the file description with a json file in it
        self.json_fd = json_fd
        # Index is our iterator that will keep track of which character we are looking at right now
        self.index = 0
        # This is used in the object member parsing to manage the special cases of missing quotes in key or value
        self.context = []
        # Use this to log the activity, but only if logging is active
        self.logger = {
            "log": [],
            "window": 10,
            "log_level": "info" if logging else "none",
        }

    def parse(self) -> Union[Dict[str, Any], List[Any], str, float, int, bool, None]:
        if self.logger["log_level"] == "none":
            return self.parse_json()
        else:
            return self.parse_json(), self.logger["log"]

    def parse_json(
        self,
    ) -> Union[Dict[str, Any], List[Any], str, float, int, bool, None]:
        char = self.get_char_at()
        # False means that we are at the end of the string provided, is the base case for recursion
        if char is False:
            return ""
        # <object> starts with '{'
        # but an object key must be a string
        elif char == "{":
            self.index += 1
            return self.parse_object()
        # <array> starts with '['
        # but an object key must be a string
        elif char == "[":
            self.index += 1
            return self.parse_array()
        # there can be an edge case in which a key is empty and at the end of an object
        # like "key": }. We return an empty string here to close the object properly
        elif char == "}":
            self.log(
                "At the end of an object we found a key with missing value, skipping",
                "info",
            )
            return ""
        # <string> starts with a quote
        elif char in ['"', "'", "“"] or char.isalpha():
            return self.parse_string()
        # <number> starts with [0-9] or minus
        elif char.isdigit() or char == "-" or char == ".":
            return self.parse_number()
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
                self.log(
                    "While parsing an object we found a : before a key, ignoring",
                    "info",
                )
                self.index += 1

            # We are now searching for they string key
            # Context is used in the string parser to manage the lack of quotes
            self.set_context("object_key")

            self.skip_whitespaces_at()

            # <member> starts with a <string>
            key = ""
            while key == "" and self.get_char_at():
                current_index = self.index
                key = self.parse_string()

                # This can happen sometimes like { "": "value" }
                if key == "" and self.get_char_at() == ":":
                    key = "empty_placeholder"
                    self.log(
                        "While parsing an object we found an empty key, replacing with empty_placeholder",
                        "info",
                    )
                    break
                elif key == "" and self.index == current_index:
                    # Sometimes the string search might not move the index at all, that might lead us to an infinite loop
                    self.index += 1

            # We reached the end here
            if (self.get_char_at() or "}") == "}":
                continue

            # An extreme case of missing ":" after a key
            if (self.get_char_at() or "") != ":":
                self.log(
                    "While parsing an object we missed a : after a key",
                    "info",
                )

            self.index += 1
            self.reset_context()
            self.set_context("object_value")
            # The value can be any valid json
            value = self.parse_json()

            # Reset context since our job is done
            self.reset_context()
            obj[key] = value

            if (self.get_char_at() or "") in [",", "'", '"']:
                self.index += 1

            # Remove trailing spaces
            self.skip_whitespaces_at()

        # Especially at the end of an LLM generated json you might miss the last "}"
        if (self.get_char_at() or "}") != "}":
            self.log(
                "While parsing an object, we couldn't find the closing }, ignoring",
                "info",
            )

        self.index += 1
        return obj

    def parse_array(self) -> List[Any]:
        # <array> ::= '[' [ <json> *(', ' <json>) ] ']' ; A sequence of JSON values separated by commas
        arr = []
        self.set_context("array")
        # Stop when you either find the closing parentheses or you have iterated over the entire string
        while (self.get_char_at() or "]") != "]":
            self.skip_whitespaces_at()
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
            if self.get_context() == "object_value" and char == "}":
                self.log(
                    "While parsing an array inside an object, we got to the end without finding a ]. Stopped parsing",
                    "info",
                )
                break

        # Especially at the end of an LLM generated json you might miss the last "]"
        char = self.get_char_at()
        if char and char != "]":
            self.log(
                "While parsing an array we missed the closing ], adding it back", "info"
            )
            # Sometimes when you fix a missing "]" you'll have a trailing "," there that makes the JSON invalid
            if char == ",":
                # Remove trailing "," before adding the "]"
                self.log(
                    "While parsing an array, found a trailing , before adding ]",
                    "info",
                )

            self.index -= 1

        self.index += 1
        self.reset_context()
        return arr

    def parse_string(self) -> str:
        # <string> is a string of valid characters enclosed in quotes
        # i.e. { name: "John" }
        # Somehow all weird cases in an invalid JSON happen to be resolved in this function, so be careful here

        # Flag to manage corner cases related to missing starting quote
        missing_quotes = False
        doubled_quotes = False
        lstring_delimiter = rstring_delimiter = '"'

        char = self.get_char_at()
        # A valid string can only start with a valid quote or, in our case, with a literal
        while char and char not in ['"', "'", "“"] and not char.isalpha():
            self.index += 1
            char = self.get_char_at()

        if not char:
            # This is an empty string
            return ""

        # Ensuring we use the right delimiter
        if char == "'":
            lstring_delimiter = rstring_delimiter = "'"
        elif char == "“":
            lstring_delimiter = "“"
            rstring_delimiter = "”"
        elif char.isalpha():
            # This could be a <boolean> and not a string. Because (T)rue or (F)alse or (N)ull are valid
            if char.lower() in ["t", "f", "n"]:
                value = self.parse_boolean_or_null()
                if value != "":
                    return value
            self.log(
                "While parsing a string, we found a literal instead of a quote",
                "info",
            )
            if self.get_context() == "":
                # A string literal in the wild isn't a valid json and not something we can fix
                self.log(
                    "While parsing a string, we found a literal outside of context, ignoring it",
                    "info",
                )
                self.index += 1
                return self.parse_json()
            self.log(
                "While parsing a string, we found no starting quote, ignoring", "info"
            )
            missing_quotes = True

        if not missing_quotes:
            self.index += 1

        # There is sometimes a weird case of doubled quotes, we manage this also later in the while loop
        if self.get_char_at() == lstring_delimiter:
            # This is a valid exception only if it's closed by a double delimiter again
            i = 1
            next_c = self.get_char_at(i)
            while next_c and next_c != rstring_delimiter:
                i += 1
                next_c = self.get_char_at(i)
            # Now check that the next character is also a delimiter to ensure that we have "".....""
            # In that case we ignore this rstring delimiter
            if next_c and (self.get_char_at(i + 1) or "") == rstring_delimiter:
                self.log(
                    "While parsing a string, we found a valid starting doubled quote, ignoring it",
                    "info",
                )
                doubled_quotes = True
                self.index += 1

        # Initialize our return value
        string_acc = ""

        # Here things get a bit hairy because a string missing the final quote can also be a key or a value in an object
        # In that case we need to use the ":|,|}" characters as terminators of the string
        # So this will stop if:
        # * It finds a closing quote
        # * It iterated over the entire sequence
        # * If we are fixing missing quotes in an object, when it finds the special terminators
        char = self.get_char_at()
        while char and char != rstring_delimiter:
            if missing_quotes:
                if self.get_context() == "object_key" and (
                    char == ":" or char.isspace()
                ):
                    break
                elif self.get_context() == "object_value" and char in [",", "}"]:
                    break
            string_acc += char
            self.index += 1
            char = self.get_char_at()
            # ChatGPT sometimes forget to quote stuff in html tags or markdown, so we do this whole thing here
            if char == rstring_delimiter:
                # Special case here, in case of double quotes one after another
                if doubled_quotes and self.get_char_at(1) == rstring_delimiter:
                    self.log(
                        "While parsing a string, we found a doubled quote, ignoring it",
                        "info",
                    )
                else:
                    # Check if eventually there is a rstring delimiter, otherwise we bail
                    i = 1
                    next_c = self.get_char_at(i)
                    while next_c and next_c != rstring_delimiter:
                        # If we are in an object context, let's check for the right delimiters
                        if (
                            next_c == lstring_delimiter
                            or ("object_key" in self.context and next_c == ":")
                            or ("object_value" in self.context and next_c in ["}", ","])
                            or ("array" in self.context and next_c in ["]", ","])
                        ):
                            break
                        i += 1
                        next_c = self.get_char_at(i)
                    if next_c == rstring_delimiter:
                        # But this might not be it! This could be just a missing comma
                        # We need to check if we find a rstring_delimiter and a colon after
                        i += 1
                        next_c = self.get_char_at(i)
                        while next_c and next_c != rstring_delimiter:
                            i += 1
                            next_c = self.get_char_at(i)
                        i += 1
                        next_c = self.get_char_at(i)
                        while next_c and next_c != ":":
                            if next_c in [lstring_delimiter, rstring_delimiter, ","]:
                                break
                            i += 1
                            next_c = self.get_char_at(i)
                        # Only if we fail to find a ':' then we know this is misplaced quote
                        if next_c != ":":
                            self.log(
                                "While parsing a string, we a misplaced quote that would have closed the string but has a different meaning here, ignoring it",
                                "info",
                            )
                            string_acc += char
                            self.index += 1
                            char = self.get_char_at()

        if (
            char
            and missing_quotes
            and self.get_context() == "object_key"
            and char.isspace()
        ):
            self.log(
                "While parsing a string, handling an extreme corner case in which the LLM added a comment instead of valid string, invalidate the string and return an empty value",
                "info",
            )
            self.skip_whitespaces_at()
            if self.get_char_at() not in [":", ","]:
                return ""

        # A fallout of the previous special case in the while loop, we need to update the index only if we had a closing quote
        if char != rstring_delimiter:
            self.log(
                "While parsing a string, we missed the closing quote, ignoring",
                "info",
            )
        else:
            self.index += 1

        return string_acc.rstrip()

    def parse_number(self) -> Union[float, int, str]:
        # <number> is a valid real number expressed in one of a number of given formats
        number_str = ""
        number_chars = set("0123456789-.eE/,")
        char = self.get_char_at()
        while char and char in number_chars:
            number_str += char
            self.index += 1
            char = self.get_char_at()
        if len(number_str) > 1 and number_str[-1] in "-eE/,":
            # The number ends with a non valid character for a number/currency, rolling back one
            number_str = number_str[:-1]
            self.index -= 1
        if number_str:
            try:
                if "," in number_str:
                    return str(number_str)
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
            # If nothing works, let's skip and keep parsing
            return self.parse_json()

    def parse_boolean_or_null(self) -> Union[bool, str, None]:
        # <boolean> is one of the literal strings 'true', 'false', or 'null' (unquoted)
        starting_index = self.index
        value = ""
        char = self.get_char_at().lower()
        if char == "t":
            value = ("true", True)
        elif char == "f":
            value = ("false", False)
        elif char == "n":
            value = ("null", None)

        if len(value):
            i = 0
            while char and i < len(value[0]) and char == value[0][i]:
                i += 1
                self.index += 1
                char = self.get_char_at().lower()
            if i == len(value[0]):
                return value[1]

        # If nothing works reset the index before returning
        self.index = starting_index
        return ""

    def get_char_at(self, count: int = 0) -> Union[str, bool]:
        # Why not use something simpler? Because try/except in python is a faster alternative to an "if" statement that is often True
        try:
            return self.json_str[self.index + count]
        except IndexError:
            if self.json_fd:
                self.json_fd.seek(self.index + count)
                char = self.json_fd.read(1)
                if char == "":
                    return False
                return char
            else:
                return False

    def skip_whitespaces_at(self) -> None:
        """
        This function quickly iterates on whitespaces, syntactic sugar to make the code more concise
        """
        if self.json_fd:
            char = self.get_char_at()
            while char and char.isspace():
                self.index += 1
                char = self.get_char_at()
        else:
            # If this is not a file stream, we do this monster here to make this function much much faster
            try:
                char = self.json_str[self.index]
            except IndexError:
                return
            while char.isspace():
                self.index += 1
                try:
                    char = self.json_str[self.index]
                except IndexError:
                    return

    def set_context(self, value: str) -> None:
        # If a value is provided update the context variable and save in stack
        if value:
            self.context.append(value)

    def reset_context(self) -> None:
        try:
            self.context.pop()
        except Exception:
            return

    def get_context(self) -> str:
        try:
            return self.context[-1]
        except Exception:
            return ""

    def log(self, text: str, level: str) -> None:
        if level == self.logger["log_level"]:
            context = ""
            if self.json_fd:
                self.json_fd.seek(self.index - self.logger["window"])
                context = self.json_fd.read(self.logger["window"] * 2)
                self.json_fd.seek(self.index)
            else:
                start = (
                    self.index - self.logger["window"]
                    if (self.index - self.logger["window"]) >= 0
                    else 0
                )
                end = (
                    self.index + self.logger["window"]
                    if (self.index + self.logger["window"]) <= len(self.json_str)
                    else len(self.json_str)
                )
                context = self.json_str[start:end]
            self.logger["log"].append(
                {
                    "text": text,
                    "context": context,
                }
            )


def repair_json(
    json_str: str = "",
    return_objects: bool = False,
    skip_json_loads: bool = False,
    logging: bool = False,
    json_fd: TextIO = None,
) -> Union[Dict[str, Any], List[Any], str, float, int, bool, None]:
    """
    Given a json formatted string, it will try to decode it and, if it fails, it will try to fix it.
    It will return the fixed string by default.
    When `return_objects=True` is passed, it will return the decoded data structure instead.
    When `skip_json_loads=True` is passed, it will not call the built-in json.loads() function
    When `logging=True` is passed, it will return an tuple with the repaired json and a log of all repair actions
    """
    parser = JSONParser(json_str, json_fd, logging)
    if skip_json_loads:
        parsed_json = parser.parse()
    else:
        try:
            if json_fd:
                parsed_json = json.load(json_fd)
            else:
                parsed_json = json.loads(json_str)
        except json.JSONDecodeError:
            parsed_json = parser.parse()
    # It's useful to return the actual object instead of the json string, it allows this lib to be a replacement of the json library
    if return_objects or logging:
        return parsed_json
    return json.dumps(parsed_json)


def loads(
    json_str: str, skip_json_loads: bool = False, logging: bool = False
) -> Union[Dict[str, Any], List[Any], str, float, int, bool, None]:
    """
    This function works like `json.loads()` except that it will fix your JSON in the process.
    It is a wrapper around the `repair_json()` function with `return_objects=True`.
    """
    return repair_json(
        json_str=json_str,
        return_objects=True,
        skip_json_loads=skip_json_loads,
        logging=logging,
    )


def load(
    fd: TextIO, skip_json_loads: bool = False, logging: bool = False
) -> Union[Dict[str, Any], List[Any], str, float, int, bool, None]:
    """
    This function works like `json.load()` except that it will fix your JSON in the process.
    It is a wrapper around the `repair_json()` function with `json_fd=fd` and `return_objects=True`.
    """
    return repair_json(json_fd=fd, skip_json_loads=skip_json_loads, logging=logging)


def from_file(
    filename: str, skip_json_loads: bool = False, logging: bool = False
) -> Union[Dict[str, Any], List[Any], str, float, int, bool, None]:
    """
    This function is a wrapper around `load()` so you can pass the filename as string
    """
    fd = open(filename)
    jsonobj = load(fd, skip_json_loads, logging)
    fd.close()

    return jsonobj
