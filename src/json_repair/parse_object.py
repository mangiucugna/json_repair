from .constants import JSONReturnType
from .json_context import ContextValues


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
                                new_array[0] if len(new_array) == 1 and isinstance(new_array[0], list) else new_array
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
            self.json_str = self.json_str[: self.index + 1] + "{" + self.json_str[self.index + 1 :]
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
        self.skip_whitespaces_at()
        # Corner case, a lone comma
        value: JSONReturnType = ""
        if (self.get_char_at() or "") in [",", "}"]:
            self.log(
                "While parsing an object value we found a stray , ignoring it",
            )
        else:
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
