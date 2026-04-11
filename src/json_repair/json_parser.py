from collections.abc import Callable
from typing import TYPE_CHECKING, Any, TextIO

from .parse_array import parse_array as _parse_array
from .parse_comment import parse_comment as _parse_comment
from .parse_number import parse_number as _parse_number
from .parse_object import parse_object as _parse_object
from .parse_string import parse_string as _parse_string
from .utils.constants import STRING_DELIMITERS, JSONReturnType
from .utils.json_context import JsonContext
from .utils.object_comparer import ObjectComparer
from .utils.string_file_wrapper import StringFileWrapper

if TYPE_CHECKING:
    from .schema_repair import SchemaRepairer


class JSONParser:
    # Split the parse methods into separate files because this one was like 3000 lines
    def parse_array(
        self,
        schema: dict[str, Any] | bool | None = None,
        path: str = "$",
        closing_delimiter: str = "]",
    ) -> list[JSONReturnType]:
        return _parse_array(self, schema, path, closing_delimiter)

    def parse_comment(self) -> JSONReturnType:
        return _parse_comment(self)

    def parse_number(self) -> JSONReturnType:
        return _parse_number(self)

    def parse_object(
        self,
        schema: dict[str, Any] | bool | None = None,
        path: str = "$",
    ) -> JSONReturnType:
        return _parse_object(self, schema, path)

    def parse_string(self) -> JSONReturnType:
        return _parse_string(self)

    def __init__(
        self,
        json_str: str | StringFileWrapper,
        json_fd: TextIO | None,
        logging: bool | None,
        json_fd_chunk_length: int = 0,
        stream_stable: bool = False,
        strict: bool = False,
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
        self.logger: list[dict[str, str]] = []
        if logging:
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
        # Over time the library got more and more complex heuristics to repair JSON. Some of these heuristics
        # may not be desirable in some use cases and the user would prefer json_repair to return an exception.
        # So strict mode was added to disable some of those heuristics.
        self.strict = strict
        self.schema_repairer: SchemaRepairer | None = None

    def parse(
        self,
    ) -> JSONReturnType:
        return self._parse_top_level(self.parse_json)

    def parse_with_schema(
        self,
        repairer: "SchemaRepairer",
        schema: dict[str, Any] | bool,
    ) -> JSONReturnType:
        """Parse with schema guidance enabled for all nested values."""
        self.schema_repairer = repairer
        return self._parse_top_level(lambda: self.parse_json(schema, "$"))

    # Consolidate top-level parsing so we handle multiple sequential JSON values consistently
    # (including update semantics and strict-mode validation).
    def _parse_top_level(self, parse_element: Callable[[], JSONReturnType]) -> JSONReturnType:
        json = parse_element()
        if self.index < len(self.json_str):
            self.log(
                "The parser returned early, checking if there's more json elements",
            )
            json = [json]
            while self.index < len(self.json_str):
                self.context.reset()
                j = parse_element()
                if j:
                    if ObjectComparer.is_same_object(json[-1], j):
                        # Treat repeated objects as updates: keep the newest value.
                        json.pop()
                    else:
                        if not json[-1]:
                            json.pop()
                    json.append(j)
                else:
                    self.index += 1
            if len(json) == 1:
                self.log(
                    "There were no more elements, returning the element without the array",
                )
                json = json[0]
            elif self.strict:
                self.log(
                    "Multiple top-level JSON elements found in strict mode, raising an error",
                )
                raise ValueError("Multiple top-level JSON elements found in strict mode.")
        return json

    def parse_json(
        self,
        schema: dict[str, Any] | bool | None = None,
        path: str = "$",
    ) -> JSONReturnType:
        """Parse the next JSON value and, when configured, enforce schema constraints."""
        repairer = self.schema_repairer if self.schema_repairer is not None and schema not in (None, True) else None
        if repairer is not None:
            # Resolve references once and decide whether schema-guided repairs are needed.
            schema = repairer.resolve_schema(schema)
            if schema is True:
                repairer = None
            elif schema is False:
                raise ValueError("Schema does not allow any values.")

        while True:
            char = self.get_char_at()
            # None means that we are at the end of the string provided
            if char is None:
                return ""
            # <object> starts with '{'
            if char == "{":
                self.index += 1
                value = self.parse_object(schema, path) if repairer else self.parse_object()
                return repairer.repair_value(value, schema, path) if repairer else value
            # <array> starts with '['
            if char == "[":
                self.index += 1
                value = self.parse_array(schema, path) if repairer else self.parse_array()
                return repairer.repair_value(value, schema, path) if repairer else value
            # Python tuple literals and grouped values start with '('
            if char == "(":
                # Keep top-level tuple detection conservative so inline prose like
                # "note (clarification):" does not hijack later JSON blocks.
                if not self.context.empty or self.top_level_parenthesized_can_start_value():
                    value = self.parse_parenthesized(schema, path) if repairer else self.parse_parenthesized()
                    return repairer.repair_value(value, schema, path) if repairer else value
                self.index += 1
                continue
            # <string> starts with a quote
            if not self.context.empty and (char in STRING_DELIMITERS or char.isalpha()):
                value = self.parse_string()
                return repairer.repair_value(value, schema, path) if repairer else value
            # <number> starts with [0-9] or minus
            if not self.context.empty and (char.isdigit() or char == "-" or char == "."):
                value = self.parse_number()
                return repairer.repair_value(value, schema, path) if repairer else value
            if char in ["#", "/"]:
                value = self.parse_comment()
                return repairer.repair_value(value, schema, path) if repairer else value
            # If everything else fails, we just ignore and move on
            self.index += 1

    def get_char_at(self, count: int = 0) -> str | None:
        # Why not use something simpler? Because try/except in python is a faster alternative to an "if" statement that is often True
        try:
            return self.json_str[self.index + count]
        except IndexError:
            return None

    def skip_whitespaces(self) -> None:
        """
        This function quickly iterates on whitespaces, moving the self.index forward
        """
        try:
            char = self.json_str[self.index]
            while char.isspace():
                self.index += 1
                char = self.json_str[self.index]
        except IndexError:
            pass

    def scroll_whitespaces(self, idx: int = 0) -> int:
        """
        This function quickly iterates on whitespaces. Doesn't move the self.index and returns the offset from self.index
        """
        try:
            char = self.json_str[self.index + idx]
            while char.isspace():
                idx += 1
                char = self.json_str[self.index + idx]
        except IndexError:
            pass
        return idx

    def skip_to_character(self, character: str | list[str], idx: int = 0) -> int:
        """
        Advance from (self.index + idx) until we hit an *unescaped* target character.
        Returns the offset (idx) from self.index to that position, or the distance to the end if not found.
        """
        targets = set(character) if isinstance(character, list) else {character}
        i = self.index + idx
        n = len(self.json_str)
        backslashes = 0  # count of consecutive '\' immediately before current char

        while i < n:
            ch = self.json_str[i]

            if ch == "\\":
                backslashes += 1
                i += 1
                continue

            # ch is not a backslash; if it's a target and not escaped (even backslashes), we're done
            if ch in targets and (backslashes % 2 == 0):
                return i - self.index

            # reset backslash run when we see a non-backslash
            backslashes = 0
            i += 1

        # not found; return distance to end
        return n - self.index

    def parenthesized_is_explicit_tuple(self) -> bool:
        """
        Return True when the current '(' starts an explicit Python tuple literal.

        Empty parentheses count as a tuple. A single grouped value like ``(1)`` does not.
        """
        i = self.index + 1
        n = len(self.json_str)
        nested_parentheses = 0
        square_brackets = 0
        braces = 0
        in_quote: str | None = None
        backslashes = 0
        saw_top_level_content = False

        while i < n:
            ch = self.json_str[i]

            if ch == "\\":
                backslashes += 1
                i += 1
                continue

            if in_quote is not None:
                if ch == in_quote and backslashes % 2 == 0:
                    in_quote = None
                backslashes = 0
                i += 1
                continue

            if ch in STRING_DELIMITERS and backslashes % 2 == 0:
                in_quote = ch
                saw_top_level_content = saw_top_level_content or (
                    nested_parentheses == 0 and square_brackets == 0 and braces == 0
                )
                backslashes = 0
                i += 1
                continue

            backslashes = 0

            if (
                not ch.isspace()
                and ch not in [",", ")"]
                and nested_parentheses == 0
                and square_brackets == 0
                and braces == 0
            ):
                saw_top_level_content = True

            if ch == "(":
                nested_parentheses += 1
            elif ch == ")":
                if nested_parentheses == 0 and square_brackets == 0 and braces == 0:
                    return not saw_top_level_content
                if nested_parentheses > 0:
                    nested_parentheses -= 1
            elif ch == "[":
                square_brackets += 1
            elif ch == "]" and square_brackets > 0:
                square_brackets -= 1
            elif ch == "{":
                braces += 1
            elif ch == "}" and braces > 0:
                braces -= 1
            elif ch == "," and nested_parentheses == 0 and square_brackets == 0 and braces == 0:
                return True

            i += 1

        return not saw_top_level_content

    def top_level_parenthesized_can_start_value(self) -> bool:
        """
        Return True when a top-level '(' looks like a standalone value rather than inline prose.

        This keeps tuple support available for direct inputs and fenced blocks while avoiding
        regressions on surrounding explanatory text like ``foo (clarification): {...}``.
        """
        i = self.index - 1
        while i >= 0:
            ch = self.json_str[i]
            if ch in "\n\r":
                break
            if not ch.isspace():
                return False
            i -= 1

        idx = self.scroll_whitespaces(idx=1)
        first_inner_char = self.get_char_at(idx)
        if first_inner_char is None:
            return False

        if (
            first_inner_char not in [")", "{", "[", "(", *STRING_DELIMITERS]
            and not first_inner_char.isdigit()
            and first_inner_char not in ["-", "."]
            and self.json_str[self.index + idx : self.index + idx + 4] not in ["true", "null"]
            and self.json_str[self.index + idx : self.index + idx + 5] != "false"
        ):
            return False

        i = self.index + 1
        n = len(self.json_str)
        nested_parentheses = 0
        square_brackets = 0
        braces = 0
        in_quote: str | None = None
        backslashes = 0

        while i < n:
            ch = self.json_str[i]

            if ch == "\\":
                backslashes += 1
                i += 1
                continue

            if in_quote is not None:
                if ch == in_quote and backslashes % 2 == 0:
                    in_quote = None
                backslashes = 0
                i += 1
                continue

            if ch in STRING_DELIMITERS and backslashes % 2 == 0:
                in_quote = ch
                backslashes = 0
                i += 1
                continue

            backslashes = 0

            if ch == "(":
                nested_parentheses += 1
            elif ch == ")":
                if nested_parentheses == 0 and square_brackets == 0 and braces == 0:
                    i += 1
                    while i < n:
                        trailer = self.json_str[i]
                        if trailer in "\n\r":
                            return True
                        if not trailer.isspace():
                            return False
                        i += 1
                    return True
                nested_parentheses -= 1
            elif ch == "[":
                square_brackets += 1
            elif ch == "]" and square_brackets > 0:
                square_brackets -= 1
            elif ch == "{":
                braces += 1
            elif ch == "}" and braces > 0:
                braces -= 1

            i += 1

        return True

    def parse_parenthesized(
        self,
        schema: dict[str, Any] | bool | None = None,
        path: str = "$",
    ) -> JSONReturnType:
        explicit_tuple = self.parenthesized_is_explicit_tuple()
        self.index += 1
        values = self.parse_array(schema, path, closing_delimiter=")")
        if explicit_tuple or len(values) != 1:
            return values
        return values[0]

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
