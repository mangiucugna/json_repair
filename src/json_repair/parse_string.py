from dataclasses import dataclass, field
from typing import TYPE_CHECKING, cast

from .parse_string_helpers.object_value_context import classify_object_value_comma, update_inline_container_stack
from .parse_string_helpers.parse_boolean_or_null import parse_boolean_or_null
from .parse_string_helpers.parse_json_llm_block import parse_json_llm_block
from .utils.constants import STRING_DELIMITERS, JSONReturnType
from .utils.json_context import ContextValues

if TYPE_CHECKING:
    from .json_parser import JSONParser


NO_DIRECT_RESULT = object()
INLINE_CONTAINER_CLOSING_DELIMITERS = {"[": "]", "{": "}", "(": ")"}
INLINE_CONTAINER_OPENERS = tuple(INLINE_CONTAINER_CLOSING_DELIMITERS)


@dataclass
class StringParseState:
    missing_quotes: bool = False
    doubled_quotes: bool = False
    lstring_delimiter: str = '"'
    rstring_delimiter: str = '"'
    string_acc: str = ""
    unmatched_delimiter: bool = False
    pending_inline_container: bool = False
    inline_container_stack: list[str] = field(default_factory=list)


def _try_parse_simple_quoted_string(self: "JSONParser") -> str | None:
    if self.get_char_at() != '"':
        return None

    start = self.index + 1
    json_str = self.json_str
    if isinstance(json_str, str):
        end = json_str.find('"', start)
        if end == -1:
            return None
        value = json_str[start:end]
        if "\\" in value or "\n" in value or "\r" in value:
            return None
    else:
        end = start
        limit = len(json_str)
        while end < limit:
            char = json_str[end]
            if char == '"':
                break
            if char in {"\\", "\n", "\r"}:
                return None
            end += 1
        if end >= limit:
            return None
        value = json_str[start:end]

    next_index = end + 1
    limit = len(json_str)
    while next_index < limit and self.json_str[next_index].isspace():
        next_index += 1
    next_char = self.json_str[next_index] if next_index < limit else None

    current_context = self.context.current
    if current_context == ContextValues.OBJECT_KEY:
        if next_char != ":":
            return None
    elif current_context == ContextValues.OBJECT_VALUE:
        if next_char not in {",", "}", None}:
            return None
    elif current_context == ContextValues.ARRAY:
        if next_char not in {",", "]", None}:
            return None
    elif next_char is not None:
        return None

    self.index = end + 1
    return value


def _append_literal_char(
    self: "JSONParser",
    state: StringParseState,
    current_char: str,
) -> str | None:
    state.string_acc += current_char
    self.index += 1
    return self.get_char_at()


def _prepare_string_entry(
    self: "JSONParser",
) -> tuple[StringParseState, object]:
    state = StringParseState()

    char = self.get_char_at()
    if char in ["#", "/"]:
        return state, self.parse_comment()

    while char and char not in STRING_DELIMITERS and not char.isalnum():
        self.index += 1
        char = self.get_char_at()

    if not char:
        return state, ""

    fast_path_value = _try_parse_simple_quoted_string(self)
    if fast_path_value is not None:
        return state, fast_path_value

    if char == "'":
        state.lstring_delimiter = state.rstring_delimiter = "'"
    elif char == "“":
        state.lstring_delimiter = "“"
        state.rstring_delimiter = "”"
    elif char.isalnum():
        if char.lower() in ["t", "f", "n"] and self.context.current != ContextValues.OBJECT_KEY:
            value = parse_boolean_or_null(self)
            if value != "":
                return state, value
        self.log(
            "While parsing a string, we found a literal instead of a quote",
        )
        state.missing_quotes = True

    if not state.missing_quotes:
        self.index += 1
    if self.get_char_at() == "`":
        ret_val = parse_json_llm_block(self)
        if ret_val is not False:
            return state, ret_val
        self.log(
            "While parsing a string, we found code fences but they did not enclose valid JSON, continuing parsing the string",
        )

    if self.get_char_at() == state.lstring_delimiter:
        if (
            (self.context.current == ContextValues.OBJECT_KEY and self.get_char_at(1) == ":")
            or (self.context.current == ContextValues.OBJECT_VALUE and self.get_char_at(1) in [",", "}"])
            or (self.context.current == ContextValues.ARRAY and self.get_char_at(1) in [",", "]"])
        ):
            self.index += 1
            return state, ""
        if self.get_char_at(1) == state.lstring_delimiter:
            self.log(
                "While parsing a string, we found a doubled quote and then a quote again, ignoring it",
            )
            if self.strict:
                raise ValueError("Found doubled quotes followed by another quote.")
            return state, ""
        i = self.skip_to_character(character=state.rstring_delimiter, idx=1)
        if self.get_char_at(i + 1) == state.rstring_delimiter:
            self.log(
                "While parsing a string, we found a valid starting doubled quote",
            )
            state.doubled_quotes = True
            self.index += 1
        else:
            i = self.scroll_whitespaces(idx=1)
            next_c = self.get_char_at(i)
            if next_c in [*STRING_DELIMITERS, "{", "["]:
                self.log(
                    "While parsing a string, we found a doubled quote but also another quote afterwards, ignoring it",
                )
                if self.strict:
                    raise ValueError(
                        "Found doubled quotes followed by another quote while parsing a string.",
                    )
                self.index += 1
                return state, ""
            if next_c not in [",", "]", "}"]:
                self.log(
                    "While parsing a string, we found a doubled quote but it was a mistake, removing one quote",
                )
                self.index += 1

    return state, NO_DIRECT_RESULT


def _normalize_escape_sequence(
    self: "JSONParser",
    state: StringParseState,
    char: str,
) -> tuple[bool, str | None]:
    self.log("Found a stray escape sequence, normalizing it")
    if char in [state.rstring_delimiter, "t", "n", "r", "b", "\\"]:
        state.string_acc = state.string_acc[:-1]
        escape_seqs = {"t": "\t", "n": "\n", "r": "\r", "b": "\b"}
        state.string_acc += escape_seqs.get(char, char)
        self.index += 1
        next_char = self.get_char_at()
        while (
            next_char
            and state.string_acc
            and state.string_acc[-1] == "\\"
            and next_char in [state.rstring_delimiter, "\\"]
        ):
            state.string_acc = state.string_acc[:-1] + next_char
            self.index += 1
            next_char = self.get_char_at()
        return True, next_char
    if char in ["u", "x"]:
        num_chars = 4 if char == "u" else 2
        next_chars = self.json_str[self.index + 1 : self.index + 1 + num_chars]
        if len(next_chars) == num_chars and all(c in "0123456789abcdefABCDEF" for c in next_chars):
            self.log("Found a unicode escape sequence, normalizing it")
            state.string_acc = state.string_acc[:-1] + chr(int(next_chars, 16))
            self.index += 1 + num_chars
            return True, self.get_char_at()
    elif char in STRING_DELIMITERS and char != state.rstring_delimiter:
        self.log("Found a delimiter that was escaped but shouldn't be escaped, removing the escape")
        state.string_acc = state.string_acc[:-1] + char
        self.index += 1
        return True, self.get_char_at()
    return False, char


def _brace_before_code_fence_belongs_to_string(
    self: "JSONParser",
    state: StringParseState,
    fence_idx: int,
) -> bool:
    # Distinguish trailing wrapper fences from literal fenced snippets inside the current string.
    quote_search_idx = fence_idx + 3
    next_content_idx = _scroll_comment_prefixed_member_start(self, quote_search_idx)
    keep_post_fence_container = False
    if self.get_char_at(next_content_idx) in INLINE_CONTAINER_OPENERS:
        container_end_idx = _skip_inline_container(self, next_content_idx)
        if container_end_idx is not None:
            if _post_fence_container_starts_next_member(self, container_end_idx):
                return False
            keep_post_fence_container = True
            quote_search_idx = container_end_idx

    quote_idx = self.skip_to_character(character=state.rstring_delimiter, idx=quote_search_idx)
    while self.get_char_at(quote_idx) == state.rstring_delimiter:
        after_quote_idx = self.scroll_whitespaces(idx=quote_idx + 1)
        after_quote = self.get_char_at(after_quote_idx)
        if after_quote in [",", "}", "]", None]:
            if keep_post_fence_container:
                state.pending_inline_container = True
            return True
        quote_idx = self.skip_to_character(character=state.rstring_delimiter, idx=quote_idx + 1)
    return False


def _matching_string_delimiter(delimiter: str) -> str:
    return "”" if delimiter == "“" else delimiter


def _bare_key_is_followed_by_colon(
    self: "JSONParser",
    key_idx: int,
) -> bool:
    key_char = self.get_char_at(key_idx)
    if not key_char or not (key_char.isalnum() or key_char == "_"):
        return False

    while True:
        key_char = self.get_char_at(key_idx)
        if not key_char or not (key_char.isalnum() or key_char in ["_", "-"]):
            break
        key_idx += 1

    key_idx = self.scroll_whitespaces(idx=key_idx)
    return self.get_char_at(key_idx) == ":"


def _post_fence_container_starts_next_member(
    self: "JSONParser",
    container_end_idx: int,
) -> bool:
    after_container_idx = self.scroll_whitespaces(idx=container_end_idx)
    after_container = self.get_char_at(after_container_idx)
    if after_container in ["}", None]:
        return True
    if after_container != ",":
        return False

    next_member_idx = _scroll_comment_prefixed_member_start(self, after_container_idx + 1)
    return self.get_char_at(next_member_idx) in ["}", None] or _object_member_starts_at(self, next_member_idx)


def _starts_nested_inline_container(
    self: "JSONParser",
    idx: int,
) -> bool:
    opening_delimiter = self.get_char_at(idx)
    prev_idx = idx - 1
    while prev_idx >= 0:
        prev_char = self.get_char_at(prev_idx)
        if prev_char is None:
            return True
        if not prev_char.isspace():
            if prev_char in INLINE_CONTAINER_OPENERS:
                return True
            if prev_char not in [",", ":"]:
                return False

            next_idx = self.scroll_whitespaces(idx=idx + 1)
            next_char = self.get_char_at(next_idx)
            if opening_delimiter in ["[", "("]:
                return next_char in ["]", ")", *STRING_DELIMITERS, "-", *INLINE_CONTAINER_OPENERS, "t", "f", "n"] or (
                    next_char is not None and next_char.isdigit()
                )
            if opening_delimiter != "{":
                return False
            if next_char in ["}", *STRING_DELIMITERS]:
                return True
            return prev_char == ":" and _bare_key_is_followed_by_colon(self, next_idx)
        prev_idx -= 1
    return True


def _skip_inline_container(
    self: "JSONParser",
    idx: int,
) -> int | None:
    opening_delimiter = self.get_char_at(idx)
    if opening_delimiter not in INLINE_CONTAINER_CLOSING_DELIMITERS:
        return idx

    stack = [INLINE_CONTAINER_CLOSING_DELIMITERS[opening_delimiter]]
    i = idx + 1
    while stack:
        char = self.get_char_at(i)
        if not char:
            return None
        if char in STRING_DELIMITERS:
            end_delimiter = _matching_string_delimiter(char)
            i = self.skip_to_character(character=end_delimiter, idx=i + 1)
            if self.get_char_at(i) != end_delimiter:
                return None
        elif char in INLINE_CONTAINER_CLOSING_DELIMITERS and _starts_nested_inline_container(self, i):
            stack.append(INLINE_CONTAINER_CLOSING_DELIMITERS[char])
        elif char == stack[-1]:
            stack.pop()
            if not stack:
                return i + 1
        i += 1

    return None  # pragma: no cover


def _scroll_comment_prefixed_member_start(
    self: "JSONParser",
    idx: int,
) -> int:
    idx = self.scroll_whitespaces(idx=idx)
    while True:
        char = self.get_char_at(idx)
        if char == "#":
            while char and char not in ["\n", "\r"]:
                idx += 1
                char = self.get_char_at(idx)
            idx = self.scroll_whitespaces(idx=idx)
            continue
        if char == "/":
            next_char = self.get_char_at(idx + 1)
            if next_char == "/":
                idx += 2
                char = self.get_char_at(idx)
                while char and char not in ["\n", "\r"]:
                    idx += 1
                    char = self.get_char_at(idx)
                idx = self.scroll_whitespaces(idx=idx)
                continue
            if next_char == "*":
                idx += 2
                while True:
                    char = self.get_char_at(idx)
                    if not char:
                        return idx
                    if char == "*" and self.get_char_at(idx + 1) == "/":
                        idx += 2
                        break
                    idx += 1
                idx = self.scroll_whitespaces(idx=idx)
                continue
        return idx


def _quoted_object_member_follows(
    self: "JSONParser",
    quote_idx: int,
) -> bool:
    comma_idx = self.scroll_whitespaces(idx=quote_idx + 1)
    if self.get_char_at(comma_idx) != ",":
        return False

    next_member_idx = _scroll_comment_prefixed_member_start(self, comma_idx + 1)
    return _object_member_starts_at(self, next_member_idx)


def _object_member_starts_at(
    self: "JSONParser",
    next_member_idx: int,
) -> bool:
    if self.get_char_at(next_member_idx) in ["}", None]:
        return False

    next_member = self.get_char_at(next_member_idx)
    if next_member in STRING_DELIMITERS:
        key_end_delimiter = _matching_string_delimiter(next_member)
        key_end_idx = self.skip_to_character(character=key_end_delimiter, idx=next_member_idx + 1)
        if self.get_char_at(key_end_idx) != key_end_delimiter:
            return False
        after_key_idx = self.scroll_whitespaces(idx=key_end_idx + 1)
        return self.get_char_at(after_key_idx) == ":"

    if next_member and (next_member.isalnum() or next_member == "_"):
        return _bare_key_is_followed_by_colon(self, next_member_idx)

    return False


def _handle_right_delimiter_candidate(
    self: "JSONParser",
    state: StringParseState,
    char: str,
) -> tuple[bool, str | None, bool]:
    if state.doubled_quotes and self.get_char_at(1) == state.rstring_delimiter:
        self.log("While parsing a string, we found a doubled quote, ignoring it")
        self.index += 1
        return True, char, False

    if state.missing_quotes and self.context.current == ContextValues.OBJECT_VALUE:
        i = 1
        next_c = self.get_char_at(i)
        while next_c and next_c not in [
            state.rstring_delimiter,
            state.lstring_delimiter,
        ]:
            i += 1
            next_c = self.get_char_at(i)
        if next_c:
            i += 1
            i = self.scroll_whitespaces(idx=i)
            if self.get_char_at(i) == ":":
                self.index -= 1
                next_char = self.get_char_at()
                self.log(
                    "In a string with missing quotes and object value context, I found a delimeter but it turns out it was the beginning on the next key. Stopping here.",
                )
                return False, next_char, True
        return False, char, False

    if state.unmatched_delimiter:
        state.unmatched_delimiter = False
        next_char = _append_literal_char(self, state, char)
        return True, next_char, False

    i = 1
    next_c = self.get_char_at(i)
    check_comma_in_object_value = True
    while next_c and next_c not in [
        state.rstring_delimiter,
        state.lstring_delimiter,
    ]:
        if check_comma_in_object_value and next_c.isalpha():
            check_comma_in_object_value = False
        if (
            (ContextValues.OBJECT_KEY in self.context.context and next_c in [":", "}"])
            or (ContextValues.OBJECT_VALUE in self.context.context and next_c == "}")
            or (ContextValues.ARRAY in self.context.context and next_c in ["]", ","])
            or (check_comma_in_object_value and self.context.current == ContextValues.OBJECT_VALUE and next_c == ",")
        ):
            break
        i += 1
        next_c = self.get_char_at(i)
    if next_c == "," and self.context.current == ContextValues.OBJECT_VALUE:
        i += 1
        i = self.skip_to_character(character=state.rstring_delimiter, idx=i)
        next_c = self.get_char_at(i)
        i += 1
        i = self.scroll_whitespaces(idx=i)
        next_c = self.get_char_at(i)
        if next_c in ["}", ","]:
            self.log(
                "While parsing a string, we found a misplaced quote that would have closed the string but has a different meaning here, ignoring it",
            )
            next_char = _append_literal_char(self, state, char)
            return True, next_char, False
    elif next_c == state.rstring_delimiter and self.get_char_at(i - 1) != "\\":
        if _only_whitespace_until(self, i) and not (
            self.context.current == ContextValues.OBJECT_VALUE and _quoted_object_member_follows(self, i)
        ):
            return False, char, True
        if self.context.current == ContextValues.OBJECT_VALUE:
            if _quoted_object_member_follows(self, i):
                self.log(
                    "While parsing a string, we found a misplaced quote that would have closed the string but has a different meaning here, ignoring it",
                )
                next_char = _append_literal_char(self, state, char)
                return True, next_char, False
            i = self.skip_to_character(character=state.rstring_delimiter, idx=i + 1)
            i += 1
            next_c = self.get_char_at(i)
            while next_c and next_c != ":":
                if next_c in [",", "]", "}"] or (next_c == state.rstring_delimiter and self.get_char_at(i - 1) != "\\"):
                    break
                i += 1
                next_c = self.get_char_at(i)
            if next_c != ":":
                self.log(
                    "While parsing a string, we found a misplaced quote that would have closed the string but has a different meaning here, ignoring it",
                )
                state.unmatched_delimiter = not state.unmatched_delimiter
                next_char = _append_literal_char(self, state, char)
                return True, next_char, False
        elif self.context.current == ContextValues.ARRAY:
            even_delimiters = next_c == state.rstring_delimiter
            while next_c == state.rstring_delimiter:
                i = self.skip_to_character(character=[state.rstring_delimiter, "]"], idx=i + 1)
                next_c = self.get_char_at(i)
                if next_c != state.rstring_delimiter:
                    even_delimiters = False
                    break
                i = self.skip_to_character(character=[state.rstring_delimiter, "]"], idx=i + 1)
                next_c = self.get_char_at(i)
            if even_delimiters:
                self.log(
                    "While parsing a string in Array context, we detected a quoted section that would have closed the string but has a different meaning here, ignoring it",
                )
                state.unmatched_delimiter = not state.unmatched_delimiter
                next_char = _append_literal_char(self, state, char)
                return True, next_char, False
            return False, char, True
        elif self.context.current == ContextValues.OBJECT_KEY:
            self.log(
                "While parsing a string in Object Key context, we detected a quoted section that would have closed the string but has a different meaning here, ignoring it",
            )
            next_char = _append_literal_char(self, state, char)
            return True, next_char, False

    return False, char, False


def _scan_string_body(
    self: "JSONParser",
    state: StringParseState,
) -> str | None:
    char = self.get_char_at()
    while char and char != state.rstring_delimiter:
        if state.missing_quotes:
            if self.context.current == ContextValues.OBJECT_KEY and (char == ":" or char.isspace()):
                self.log(
                    "While parsing a string missing the left delimiter in object key context, we found a :, stopping here",
                )
                break
            if self.context.current == ContextValues.ARRAY and char in ["]", ","]:
                self.log(
                    "While parsing a string missing the left delimiter in array context, we found a ] or ,, stopping here",
                )
                break
        if state.pending_inline_container and char in INLINE_CONTAINER_OPENERS:
            container_end_idx = _skip_inline_container(self, 0)
            if container_end_idx is not None:
                self.log(
                    "While parsing a string in object value context, we found a balanced inline container that belongs to the string, keeping it",
                )
                state.pending_inline_container = False
                state.inline_container_stack.clear()
                state.string_acc += self.json_str[self.index : self.index + container_end_idx]
                self.index += container_end_idx
                char = self.get_char_at()
                continue
        if (
            not self.stream_stable
            and self.context.current == ContextValues.OBJECT_VALUE
            and char == ","
            and not state.pending_inline_container
            and not state.inline_container_stack
        ):
            comma_classification = classify_object_value_comma(self)
            if comma_classification == "member":
                self.log(
                    "While parsing a string missing the right delimiter in object value context, we found a comma that starts the next object member. Stopping here",
                )
                break
            state.pending_inline_container = comma_classification == "container"
            self.log(
                "While parsing a string in object value context, we found a comma that belongs to the string, keeping it",
            )
            char = _append_literal_char(self, state, char)
            continue
        state.pending_inline_container, keep_inline_container_char = update_inline_container_stack(
            char,
            state.pending_inline_container,
            state.inline_container_stack,
        )
        if keep_inline_container_char:
            char = _append_literal_char(self, state, char)
            continue
        if (
            not self.stream_stable
            and self.context.current == ContextValues.OBJECT_VALUE
            and char == "}"
            and (not state.string_acc or state.string_acc[-1] != state.rstring_delimiter)
        ):
            rstring_delimiter_missing = True
            self.skip_whitespaces()
            if self.get_char_at(1) == "\\":
                rstring_delimiter_missing = False
            i = self.skip_to_character(character=state.rstring_delimiter, idx=1)
            next_c = self.get_char_at(i)
            if next_c:
                i += 1
                i = self.scroll_whitespaces(idx=i)
                next_c = self.get_char_at(i)
                if not next_c or next_c in [",", "}"]:
                    rstring_delimiter_missing = False
                else:
                    i = self.skip_to_character(character=state.lstring_delimiter, idx=i)
                    next_c = self.get_char_at(i)
                    if not next_c:
                        rstring_delimiter_missing = False
                    else:
                        i = self.scroll_whitespaces(idx=i + 1)
                        next_c = self.get_char_at(i)
                        if next_c and next_c != ":":
                            rstring_delimiter_missing = False
            else:
                i = self.skip_to_character(character=":", idx=1)
                next_c = self.get_char_at(i)
                if next_c:
                    break
                i = self.scroll_whitespaces(idx=1)
                j = self.skip_to_character(character="}", idx=i)
                if j - i > 1:
                    rstring_delimiter_missing = False
                elif self.get_char_at(j):
                    for c in reversed(state.string_acc):
                        if c == "{":
                            rstring_delimiter_missing = False
                            break
            if rstring_delimiter_missing:
                self.log(
                    "While parsing a string missing the left delimiter in object value context, we found a , or } and we couldn't determine that a right delimiter was present. Stopping here",
                )
                break
        if (
            not self.stream_stable
            and char == "]"
            and ContextValues.ARRAY in self.context.context
            and (not state.string_acc or state.string_acc[-1] != state.rstring_delimiter)
        ):
            i = self.skip_to_character(state.rstring_delimiter)
            if not self.get_char_at(i):
                break
        if self.context.current == ContextValues.OBJECT_VALUE and char == "}":
            i = self.scroll_whitespaces(idx=1)
            next_c = self.get_char_at(i)
            if next_c == "`" and self.get_char_at(i + 1) == "`" and self.get_char_at(i + 2) == "`":
                if _brace_before_code_fence_belongs_to_string(self, state, i):
                    self.log(
                        "While parsing a string in object value context, we found a literal fenced snippet after }, keeping it in the string",
                    )
                    char = _append_literal_char(self, state, char)
                    continue
                self.log(
                    "While parsing a string in object value context, we found a } that closes the object before code fences, stopping here",
                )
                break
            if not next_c:
                self.log(
                    "While parsing a string in object value context, we found a } that closes the object, stopping here",
                )
                break
        state.string_acc += char
        self.index += 1
        char = self.get_char_at()
        if char is None:
            if self.stream_stable and state.string_acc and state.string_acc[-1] == "\\":
                state.string_acc = state.string_acc[:-1]
            break
        if state.string_acc and state.string_acc[-1] == "\\":
            handled_escape, char = _normalize_escape_sequence(self, state, char)
            if handled_escape:
                continue
        if char == ":" and not state.missing_quotes and self.context.current == ContextValues.OBJECT_KEY:
            i = self.skip_to_character(character=state.lstring_delimiter, idx=1)
            next_c = self.get_char_at(i)
            if next_c:
                i += 1
                i = self.skip_to_character(character=state.rstring_delimiter, idx=i)
                next_c = self.get_char_at(i)
                if next_c:
                    i += 1
                    i = self.scroll_whitespaces(idx=i)
                    ch = self.get_char_at(i)
                    if ch in [",", "}"]:
                        self.log(
                            f"While parsing a string missing the right delimiter in object key context, we found a {ch} stopping here",
                        )
                        break
            else:
                self.log(
                    "While parsing a string missing the right delimiter in object key context, we found a :, stopping here",
                )
                break
        if char == state.rstring_delimiter and state.string_acc and state.string_acc[-1] != "\\":
            assert char is not None
            handled_delimiter, char, should_break = _handle_right_delimiter_candidate(self, state, char)
            if should_break:
                break
            if handled_delimiter:
                continue
    return char


def _finalize_string_result(
    self: "JSONParser",
    state: StringParseState,
    char: str | None,
) -> str:
    if char and state.missing_quotes and self.context.current == ContextValues.OBJECT_KEY and char.isspace():
        self.log(
            "While parsing a string, handling an extreme corner case in which the LLM added a comment instead of valid string, invalidate the string and return an empty value",
        )
        self.skip_whitespaces()
        if self.get_char_at() not in [":", ","]:
            return ""

    if char != state.rstring_delimiter:
        if not self.stream_stable:
            self.log(
                "While parsing a string, we missed the closing quote, ignoring",
            )
            state.string_acc = state.string_acc.rstrip()
    else:
        self.index += 1

    if not self.stream_stable and (state.missing_quotes or (state.string_acc and state.string_acc[-1] == "\n")):
        state.string_acc = state.string_acc.rstrip()

    return state.string_acc


def parse_string(self: "JSONParser") -> JSONReturnType:
    state, direct_result = _prepare_string_entry(self)
    if direct_result is not NO_DIRECT_RESULT:
        return cast("JSONReturnType", direct_result)

    char = _scan_string_body(self, state)
    return _finalize_string_result(self, state, char)


def _only_whitespace_until(self: "JSONParser", end: int) -> bool:
    for j in range(1, end):
        c = self.get_char_at(j)
        if c is not None and not c.isspace():
            return False
    return True
