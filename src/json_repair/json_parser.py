from typing import Literal, TextIO

from .constants import STRING_DELIMITERS, JSONReturnType
from .json_context import JsonContext
from .object_comparer import ObjectComparer
from .parse_array import parse_array as _parse_array
from .parse_boolean_or_null import parse_boolean_or_null as _parse_boolean_or_null
from .parse_comment import parse_comment as _parse_comment
from .parse_number import parse_number as _parse_number
from .parse_object import parse_object as _parse_object
from .parse_string import parse_string as _parse_string
from .string_file_wrapper import StringFileWrapper


class JSONParser:
    # Split the parse methods into separate files because this one was like 3000 lines
    def parse_array(self, *args, **kwargs):
        return _parse_array(self, *args, **kwargs)

    def parse_boolean_or_null(self, *args, **kwargs):
        return _parse_boolean_or_null(self, *args, **kwargs)

    def parse_comment(self, *args, **kwargs):
        return _parse_comment(self, *args, **kwargs)

    def parse_number(self, *args, **kwargs):
        return _parse_number(self, *args, **kwargs)

    def parse_object(self, *args, **kwargs):
        return _parse_object(self, *args, **kwargs)

    def parse_string(self, *args, **kwargs):
        return _parse_string(self, *args, **kwargs)

    def __init__(
        self,
        json_str: str | StringFileWrapper,
        json_fd: TextIO | None,
        logging: bool | None,
        json_fd_chunk_length: int = 0,
        stream_stable: bool = False,
    ) -> None:
        # The string to parse
        self.json_str: str | StringFileWrapper = json_str
        # Alternatively, the file description with a json file in it
        if json_fd:
            # This is a trick we do to treat the file wrapper as an array
            self.json_str = StringFileWrapper(json_fd, json_fd_chunk_length)
        # Index is our iterator that will keep track of which character we are looking at right now
        self.index: int = 0
        # This is used in the object member parsing to manage the special cases of missing quotes in key or value
        self.context = JsonContext()
        # Use this to log the activity, but only if logging is active

        # This is a trick but a beautiful one. We call self.log in the code over and over even if it's not needed.
        # We could add a guard in the code for each call but that would make this code unreadable, so here's this neat trick
        # Replace self.log with a noop
        self.logging = logging
        if logging:
            self.logger: list[dict[str, str]] = []
            self.log = self._log
        else:
            # No-op
            self.log = lambda *args, **kwargs: None  # noqa: ARG005
        # When the json to be repaired is the accumulation of streaming json at a certain moment.
        # e.g. json obtained from llm response.
        # If this parameter to True will keep the repair results stable. For example:
        #   case 1:  '{"key": "val\\' => '{"key": "val"}'
        #   case 2:  '{"key": "val\\n' => '{"key": "val\\n"}'
        #   case 3:  '{"key": "val\\n123,`key2:value2' => '{"key": "val\\n123,`key2:value2"}'
        #   case 4:  '{"key": "val\\n123,`key2:value2`"}' => '{"key": "val\\n123,`key2:value2`"}'
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
                else:
                    # this was a bust, move the index
                    self.index += 1
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
            # <string> starts with a quote
            elif not self.context.empty and (char in STRING_DELIMITERS or char.isalpha()):
                return self.parse_string()
            # <number> starts with [0-9] or minus
            elif not self.context.empty and (char.isdigit() or char == "-" or char == "."):
                return self.parse_number()
            elif char in ["#", "/"]:
                return self.parse_comment()
            # If everything else fails, we just ignore and move on
            else:
                self.index += 1

    def get_char_at(self, count: int = 0) -> str | Literal[False]:
        # Why not use something simpler? Because try/except in python is a faster alternative to an "if" statement that is often True
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

    def skip_to_character(self, character: str | list, idx: int = 0) -> int:
        """
        This function quickly iterates to find a character, syntactic sugar to make the code more concise
        """
        try:
            char = self.json_str[self.index + idx]
        except IndexError:
            return idx
        character_list = character if isinstance(character, list) else [character]
        while char not in character_list:
            idx += 1
            try:
                char = self.json_str[self.index + idx]
            except IndexError:
                return idx
        if self.json_str[self.index + idx - 1] == "\\":
            # Ah shoot this was actually escaped, continue
            return self.skip_to_character(character, idx + 1)
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
