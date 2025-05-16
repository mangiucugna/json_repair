from typing import Any, ClassVar, Literal, TextIO

from .json_context import ContextValues, JsonContext
from .object_comparer import ObjectComparer
from .string_file_wrapper import StringFileWrapper

JSONReturnType = dict[str, Any] | list[Any] | str | float | int | bool | None


class JSONParser:
    # Constants
    STRING_DELIMITERS: ClassVar[list[str]] = ['"', "'", "“", "”"]

    def __init__(
        self,
        json_str: str | StringFileWrapper,
        json_fd: TextIO | None,
        logging: bool | None,
        json_fd_chunk_length: int = 0,
        stream_stable: bool = False,
    ) -> None:
        self.json_str: str | StringFileWrapper = json_str
        if json_fd:
            self.json_str = StringFileWrapper(json_fd, json_fd_chunk_length)
        self.index: int = 0
        self.context = JsonContext()
        self.logging = logging
        if logging:
            self.logger: list[dict[str, str]] = []
            self.log = self._log
        else:
            self.log = lambda *args, **kwargs: None
        self.stream_stable = stream_stable

    def parse(
        self,
    ) -> JSONReturnType | tuple[JSONReturnType, list[dict[str, str]]]:
        json = self.parse_json()
        if self.index < len(self.json_str):
            self.log(
                "The parser returned early, checking if there's more json elements",
            )
            json = [json]
            while self.index < len(self.json_str):
                j = self.parse_json()
                if j != "":
                    if ObjectComparer.is_same_object(json[-1], j):
                        # replace the last entry with the new one since the new one seems an update
                        json.pop()
                    json.append(j)
            # If nothing extra was found, don't return an array
            if len(json) == 1:
                self.log(
                    "There were no more elements, returning the element without the array",
                )
                json = json[0]
        if self.logging:
            return json, self.logger
        else:
            return json

    def parse_json(
        self,
    ) -> JSONReturnType:
        while True:
            char = self.get_char_at()
            # False means that we are at the end of the string provided
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
            elif self.context.current == ContextValues.OBJECT_VALUE and char == "}":
                self.log(
                    "At the end of an object we found a key with missing value, skipping",
                )
                return ""
            # <string> starts with a quote
            elif not self.context.empty and (
                char in self.STRING_DELIMITERS or char.isalpha()
            ):
                return self.parse_string()
            # <number> starts with [0-9] or minus
            elif not self.context.empty and (
                char.isdigit() or char == "-" or char == "."
            ):
                return self.parse_number()
            elif char in ["#", "/"]:
                return self.parse_comment()
            # If everything else fails, we just ignore and move on
            else:
                self.index += 1

    def parse_object(self) -> dict[str, JSONReturnType]:
        # <object> ::= '{' [ <member> *(', ' <member>) ] '}' ; A sequence of 'members'
        obj: dict[str, JSONReturnType] = {}
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
                                    new_array[0]
                                    if len(new_array) == 1
                                    and isinstance(new_array[0], list)
                                    else new_array
                                )
                            self.skip_whitespaces_at()
                            if self.get_char_at() == ",":
                                self.index += 1
                            self.skip_whitespaces_at()
                            continue
                key = str(self.parse_string())
                if key == "":
                    self.skip_whitespaces_at()
                if key != "" or (key == "" and self.get_char_at() in [":", "}"]):
                    # If the string is empty but there is a object divider, we are done here
                    break
            if ContextValues.ARRAY in self.context.context and key in obj:
                self.log(
                    "While parsing an object we found a duplicate key, closing the object here and rolling back the index",
                )
                self.index = rollback_index - 1
                # add an opening curly brace to make this work
                self.json_str = (
                    self.json_str[: self.index + 1]
                    + "{"
                    + self.json_str[self.index + 1 :]
                )
                break

            # Skip filler whitespaces
            self.skip_whitespaces_at()

            # We reached the end here
            if (self.get_char_at() or "}") == "}":
                continue

            self.skip_whitespaces_at()

            # An extreme case of missing ":" after a key
            if (self.get_char_at() or "") != ":":
                self.log(
                    "While parsing an object we missed a : after a key",
                )

            self.index += 1
            self.context.reset()
            self.context.set(ContextValues.OBJECT_VALUE)
            # The value can be any valid json
            value = self.parse_json()

            # Reset context since our job is done
            self.context.reset()
            obj[key] = value

            if (self.get_char_at() or "") in [",", "'", '"']:
                self.index += 1

            # Remove trailing spaces
            self.skip_whitespaces_at()

        self.index += 1
        return obj

    def parse_array(self) -> list[JSONReturnType]:
        # <array> ::= '[' [ <json> *(', ' <json>) ] ']' ; A sequence of JSON values separated by commas
        arr = []
        self.context.set(ContextValues.ARRAY)
        # Stop when you either find the closing parentheses or you have iterated over the entire string
        char = self.get_char_at()
        while char and char not in ["]", "}"]:
            self.skip_whitespaces_at()
            value = self.parse_json()

            # It is possible that parse_json() returns nothing valid, so we increase by 1
            if value == "":
                self.index += 1
            elif value == "..." and self.get_char_at(-1) == ".":
                self.log(
                    "While parsing an array, found a stray '...'; ignoring it",
                )
            else:
                arr.append(value)

            # skip over whitespace after a value but before closing ]
            char = self.get_char_at()
            while char and char != "]" and (char.isspace() or char == ","):
                self.index += 1
                char = self.get_char_at()

        # Especially at the end of an LLM generated json you might miss the last "]"
        if char and char != "]":
            self.log(
                "While parsing an array we missed the closing ], ignoring it",
            )

        self.index += 1

        self.context.reset()
        return arr

    def parse_string(self) -> str | bool | None:
        # <string> is a string of valid characters enclosed in quotes
        # ... (keep rest of body unchanged)
        # --- NO OPTIMIZATION in this function due to its complexity and lack of profiling data for it ---
        # (copy body exactly    ...)
        missing_quotes = False
        doubled_quotes = False
        lstring_delimiter = rstring_delimiter = '"'

        char = self.get_char_at()
        if char in ["#", "/"]:
            return self.parse_comment()
        while char and char not in self.STRING_DELIMITERS and not char.isalnum():
            self.index += 1
            char = self.get_char_at()

        if not char:
            return ""

        if char == "'":
            lstring_delimiter = rstring_delimiter = "'"
        elif char == "“":
            lstring_delimiter = "“"
            rstring_delimiter = "”"
        elif char.isalnum():
            if (
                char.lower() in ["t", "f", "n"]
                and self.context.current != ContextValues.OBJECT_KEY
            ):
                value = self.parse_boolean_or_null()
                if value != "":
                    return value
            self.log(
                "While parsing a string, we found a literal instead of a quote",
            )
            missing_quotes = True

        if not missing_quotes:
            self.index += 1

        if (
            self.get_char_at() in self.STRING_DELIMITERS
            and self.get_char_at() == lstring_delimiter
        ):
            if (
                self.context.current == ContextValues.OBJECT_KEY
                and self.get_char_at(1) == ":"
            ):
                self.index += 1
                return ""
            if self.get_char_at(1) == lstring_delimiter:
                self.log(
                    "While parsing a string, we found a doubled quote and then a quote again, ignoring it",
                )
                return ""
            i = self.skip_to_character(character=rstring_delimiter, idx=1)
            next_c = self.get_char_at(i)
            if next_c and (self.get_char_at(i + 1) or "") == rstring_delimiter:
                self.log(
                    "While parsing a string, we found a valid starting doubled quote",
                )
                doubled_quotes = True
                self.index += 1
            else:
                i = self.skip_whitespaces_at(idx=1, move_main_index=False)
                next_c = self.get_char_at(i)
                if next_c in self.STRING_DELIMITERS + ["{", "["]:
                    self.log(
                        "While parsing a string, we found a doubled quote but also another quote afterwards, ignoring it",
                    )
                    self.index += 1
                    return ""
                elif next_c not in [",", "]", "}"]:
                    self.log(
                        "While parsing a string, we found a doubled quote but it was a mistake, removing one quote",
                    )
                    self.index += 1

        string_acc = ""

        char = self.get_char_at()
        unmatched_delimiter = False
        while char and char != rstring_delimiter:
            if (
                missing_quotes
                and self.context.current == ContextValues.OBJECT_KEY
                and (char == ":" or char.isspace())
            ):
                self.log(
                    "While parsing a string missing the left delimiter in object key context, we found a :, stopping here",
                )
                break
            if (
                (missing_quotes or not self.stream_stable)
                and self.context.current == ContextValues.OBJECT_VALUE
                and char in [",", "}"]
            ):
                rstring_delimiter_missing = True
                i = self.skip_to_character(character=rstring_delimiter, idx=1)
                next_c = self.get_char_at(i)
                if next_c:
                    i += 1
                    i = self.skip_whitespaces_at(idx=i, move_main_index=False)
                    next_c = self.get_char_at(i)
                    if not next_c or next_c in [",", "}"]:
                        rstring_delimiter_missing = False
                    else:
                        i = self.skip_to_character(character=lstring_delimiter, idx=i)
                        next_c = self.get_char_at(i)
                        if not next_c:
                            rstring_delimiter_missing = False
                        else:
                            i = self.skip_whitespaces_at(idx=i + 1, move_main_index=False)
                            next_c = self.get_char_at(i)
                            if next_c and next_c != ":":
                                rstring_delimiter_missing = False
                else:
                    i = self.skip_to_character(character=":", idx=1)
                    next_c = self.get_char_at(i)
                    if next_c:
                        break
                    else:
                        i = self.skip_whitespaces_at(idx=1, move_main_index=False)
                        j = self.skip_to_character(character="}", idx=i)
                        if j - i > 1:
                            rstring_delimiter_missing = False
                        elif self.get_char_at(j):
                            for c in reversed(string_acc):
                                if c == "{":
                                    rstring_delimiter_missing = False
                                    break
                if rstring_delimiter_missing:
                    self.log(
                        "While parsing a string missing the left delimiter in object value context, we found a , or } and we couldn't determine that a right delimiter was present. Stopping here",
                    )
                    break
            if (
                (missing_quotes or not self.stream_stable)
                and char == "]"
                and ContextValues.ARRAY in self.context.context
            ):
                i = self.skip_to_character(rstring_delimiter)
                if not self.get_char_at(i):
                    break
            string_acc += char
            self.index += 1
            char = self.get_char_at()
            if self.stream_stable and not char and string_acc[-1] == "\\":
                string_acc = string_acc[:-1]
            if char and string_acc[-1] == "\\":
                self.log("Found a stray escape sequence, normalizing it")
                if char in [rstring_delimiter, "t", "n", "r", "b", "\\"]:
                    string_acc = string_acc[:-1]
                    escape_seqs = {"t": "\t", "n": "\n", "r": "\r", "b": "\b"}
                    string_acc += escape_seqs.get(char, char) or char
                    self.index += 1
                    char = self.get_char_at()
            if (
                char == ":"
                and not missing_quotes
                and self.context.current == ContextValues.OBJECT_KEY
            ):
                i = self.skip_to_character(character=lstring_delimiter, idx=1)
                next_c = self.get_char_at(i)
                if next_c:
                    i += 1
                    i = self.skip_to_character(character=rstring_delimiter, idx=i)
                    next_c = self.get_char_at(i)
                    if next_c:
                        i += 1
                        i = self.skip_whitespaces_at(idx=i, move_main_index=False)
                        next_c = self.get_char_at(i)
                        if next_c and next_c in [",", "}"]:
                            self.log(
                                "While parsing a string missing the right delimiter in object key context, we found a :, stopping here",
                            )
                            break
                else:
                    self.log(
                        "While parsing a string missing the right delimiter in object key context, we found a :, stopping here",
                    )
                    break
            if char == rstring_delimiter:
                if doubled_quotes and self.get_char_at(1) == rstring_delimiter:
                    self.log(
                        "While parsing a string, we found a doubled quote, ignoring it"
                    )
                    self.index += 1
                elif (
                    missing_quotes
                    and self.context.current == ContextValues.OBJECT_VALUE
                ):
                    i = 1
                    next_c = self.get_char_at(i)
                    while next_c and next_c not in [
                        rstring_delimiter,
                        lstring_delimiter,
                    ]:
                        i += 1
                        next_c = self.get_char_at(i)
                    if next_c:
                        i += 1
                        i = self.skip_whitespaces_at(idx=i, move_main_index=False)
                        next_c = self.get_char_at(i)
                        if next_c and next_c == ":":
                            self.index -= 1
                            char = self.get_char_at()
                            self.log(
                                "In a string with missing quotes and object value context, I found a delimeter but it turns out it was the beginning on the next key. Stopping here.",
                            )
                            break
                elif unmatched_delimiter:
                    unmatched_delimiter = False
                    string_acc += str(char)
                    self.index += 1
                    char = self.get_char_at()
                else:
                    i = 1
                    next_c = self.get_char_at(i)
                    check_comma_in_object_value = True
                    while next_c and next_c not in [
                        rstring_delimiter,
                        lstring_delimiter,
                    ]:
                        if check_comma_in_object_value and next_c.isalpha():
                            check_comma_in_object_value = False
                        if (
                            (
                                ContextValues.OBJECT_KEY in self.context.context
                                and next_c in [":", "}"]
                            )
                            or (
                                ContextValues.OBJECT_VALUE in self.context.context
                                and next_c == "}"
                            )
                            or (
                                ContextValues.ARRAY in self.context.context
                                and next_c in ["]", ","]
                            )
                            or (
                                check_comma_in_object_value
                                and self.context.current == ContextValues.OBJECT_VALUE
                                and next_c == ","
                            )
                        ):
                            break
                        i += 1
                        next_c = self.get_char_at(i)
                    if (
                        next_c == ","
                        and self.context.current == ContextValues.OBJECT_VALUE
                    ):
                        i += 1
                        i = self.skip_to_character(character=rstring_delimiter, idx=i)
                        next_c = self.get_char_at(i)
                        i += 1
                        i = self.skip_whitespaces_at(idx=i, move_main_index=False)
                        next_c = self.get_char_at(i)
                    elif (
                        next_c == rstring_delimiter and self.get_char_at(i - 1) != "\\"
                    ):
                        if all(
                            str(self.get_char_at(j)).isspace()
                            for j in range(1, i)
                            if self.get_char_at(j)
                        ):
                            break
                        if self.context.current == ContextValues.OBJECT_VALUE:
                            i = self.skip_to_character(
                                character=rstring_delimiter, idx=i + 1
                            )
                            i += 1
                            next_c = self.get_char_at(i)
                            while next_c and next_c != ":":
                                if next_c in [",", "]", "}"] or (
                                    next_c == rstring_delimiter
                                    and self.get_char_at(i - 1) != "\\"
                                ):
                                    break
                                i += 1
                                next_c = self.get_char_at(i)
                            if next_c != ":":
                                self.log(
                                    "While parsing a string, we a misplaced quote that would have closed the string but has a different meaning here, ignoring it",
                                )
                                unmatched_delimiter = not unmatched_delimiter
                                string_acc += str(char)
                                self.index += 1
                                char = self.get_char_at()
                        elif self.context.current == ContextValues.ARRAY:
                            self.log(
                                "While parsing a string in Array context, we detected a quoted section that would have closed the string but has a different meaning here, ignoring it",
                            )
                            unmatched_delimiter = not unmatched_delimiter
                            string_acc += str(char)
                            self.index += 1
                            char = self.get_char_at()
                        elif self.context.current == ContextValues.OBJECT_KEY:
                            self.log(
                                "While parsing a string in Object Key context, we detected a quoted section that would have closed the string but has a different meaning here, ignoring it",
                            )
                            string_acc += str(char)
                            self.index += 1
                            char = self.get_char_at()
        if (
            char
            and missing_quotes
            and self.context.current == ContextValues.OBJECT_KEY
            and char.isspace()
        ):
            self.log(
                "While parsing a string, handling an extreme corner case in which the LLM added a comment instead of valid string, invalidate the string and return an empty value",
            )
            self.skip_whitespaces_at()
            if self.get_char_at() not in [":", ","]:
                return ""

        if char != rstring_delimiter:
            if not self.stream_stable:
                self.log(
                    "While parsing a string, we missed the closing quote, ignoring",
                )
                string_acc = string_acc.rstrip()
        else:
            self.index += 1

        if not self.stream_stable and (
            missing_quotes or (string_acc and string_acc[-1] == "\n")
        ):
            string_acc = string_acc.rstrip()

        return string_acc

    def parse_number(self) -> float | int | str | JSONReturnType:
        # <number> is a valid real number expressed in one of a number of given formats
        # Performance improvement: cache frequently-used attributes/methods locally,
        # avoid making a set("...") in every call, and collect chars into a list.
        number_char_set = "0123456789-.eE/,"
        number_chars = []
        get_char_at = self.get_char_at  # micro-optimization: local bind
        char = get_char_at()
        is_array = self.context.current == ContextValues.ARRAY

        # Manual inline char-in-<str> is slightly faster in tight loops than set-lookup for small sets
        while char and (char in number_char_set) and (not is_array or char != ","):
            number_chars.append(char)
            self.index += 1
            char = get_char_at()

        number_str = ''.join(number_chars)
        if number_str and number_str[-1] in "-eE/,":
            # The number ends with a non valid character for a number/currency, rolling back one
            number_str = number_str[:-1]
            self.index -= 1
        elif (get_char_at() or "").isalpha():
            # this was a string instead, sorry
            self.index -= len(number_str)
            return self.parse_string()
        try:
            if "," in number_str:
                return str(number_str)
            if "." in number_str or "e" in number_str or "E" in number_str:
                return float(number_str)
            else:
                return int(number_str)
        except ValueError:
            return number_str

    def parse_boolean_or_null(self) -> bool | str | None:
        # <boolean> is one of the literal strings 'true', 'false', or 'null' (unquoted)
        starting_index = self.index
        char = (self.get_char_at() or "").lower()
        value: tuple[str, bool | None] | None
        if char == "t":
            value = ("true", True)
        elif char == "f":
            value = ("false", False)
        elif char == "n":
            value = ("null", None)

        if value:
            i = 0
            while char and i < len(value[0]) and char == value[0][i]:
                i += 1
                self.index += 1
                char = (self.get_char_at() or "").lower()
            if i == len(value[0]):
                return value[1]

        # If nothing works reset the index before returning
        self.index = starting_index
        return ""

    def parse_comment(self) -> str:
        """
        Parse code-like comments:

        - "# comment": A line comment that continues until a newline.
        - "// comment": A line comment that continues until a newline.
        - "/* comment */": A block comment that continues until the closing delimiter "*/".

        The comment is skipped over and an empty string is returned so that comments do not interfere
        with the actual JSON elements.
        """
        char = self.get_char_at()
        termination_characters = ["\n", "\r"]
        if ContextValues.ARRAY in self.context.context:
            termination_characters.append("]")
        if ContextValues.OBJECT_VALUE in self.context.context:
            termination_characters.append("}")
        if ContextValues.OBJECT_KEY in self.context.context:
            termination_characters.append(":")
        # Line comment starting with #
        if char == "#":
            comment = ""
            while char and char not in termination_characters:
                comment += char
                self.index += 1
                char = self.get_char_at()
            self.log(f"Found line comment: {comment}")
            return ""

        # Comments starting with '/'
        elif char == "/":
            next_char = self.get_char_at(1)
            # Handle line comment starting with //
            if next_char == "/":
                comment = "//"
                self.index += 2  # Skip both slashes.
                char = self.get_char_at()
                while char and char not in termination_characters:
                    comment += char
                    self.index += 1
                    char = self.get_char_at()
                self.log(f"Found line comment: {comment}")
                return ""
            # Handle block comment starting with /*
            elif next_char == "*":
                comment = "/*"
                self.index += 2  # Skip '/*'
                while True:
                    char = self.get_char_at()
                    if not char:
                        self.log(
                            "Reached end-of-string while parsing block comment; unclosed block comment."
                        )
                        break
                    comment += char
                    self.index += 1
                    if comment.endswith("*/"):
                        break
                self.log(f"Found block comment: {comment}")
                return ""
        return ""  # pragma: no cover

    def get_char_at(self, count: int = 0) -> str | Literal[False]:
        # Use try/except for speed, as per comment
        try:
            return self.json_str[self.index + count]
        except IndexError:
            return False

    def skip_whitespaces_at(self, idx: int = 0, move_main_index=True) -> int:
        """
        This function quickly iterates on whitespaces, syntactic sugar to make the code more concise
        """
        try:
            char = self.json_str[self.index + idx]
        except IndexError:
            return idx
        while char.isspace():
            if move_main_index:
                self.index += 1
            else:
                idx += 1
            try:
                char = self.json_str[self.index + idx]
            except IndexError:
                return idx
        return idx

    def skip_to_character(self, character: str, idx: int = 0) -> int:
        """
        This function quickly iterates to find a character, syntactic sugar to make the code more concise
        """
        try:
            char = self.json_str[self.index + idx]
        except IndexError:
            return idx
        while char != character:
            idx += 1
            try:
                char = self.json_str[self.index + idx]
            except IndexError:
                return idx
        return idx

    def _log(self, text: str) -> None:
        window: int = 10
        start: int = max(self.index - window, 0)
        end: int = min(self.index + window, len(self.json_str))
        context: str = self.json_str[start:end]
        self.logger.append(
            {
                "text": text,
                "context": context,
            }
        )
