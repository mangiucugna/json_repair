import json
import re


class JSONParser:
    def __init__(self, json_str):
        self.json_str = json_str
        self.index = 0
        self.context = ""

    def parse(self):
        return self.parse_json()

    def parse_json(self):
        char = self.get_char_at()
        if char is False:
            return ""
        elif char == "{":
            return self.parse_object()
        elif char == "[":
            return self.parse_array()
        elif char == '"':
            return self.parse_string()
        elif char.isdigit() or char == "-":
            return self.parse_number()
        elif char == "t" or char == "f" or char == "n":
            return self.parse_boolean_or_null()
        elif char == " ":
            self.index += 1
            return self.parse_json()
        else:
            raise ValueError("Invalid JSON format")

    def parse_object(self):
        self.context = "object"
        if self.get_char_at() != "{":
            raise ValueError("Expected '{'")
        self.index += 1

        obj = {}
        while (char := self.get_char_at()) != "}" and char is not False:
            key = self.parse_string()
            if self.get_char_at() != ":":
                self.insert_char_at(":")
            self.index += 1
            value = self.parse_json()
            obj[key] = value

            if self.get_char_at() == ",":
                self.index += 1
            if self.get_char_at() == " ":
                self.index += 1

        if self.get_char_at() != "}":
            self.insert_char_at("}")
        self.index += 1
        self.context = ""
        return obj

    def parse_array(self):
        self.context = "array"
        if self.get_char_at() != "[":
            raise ValueError("Expected '['")
        self.index += 1

        arr = []
        while (char := self.get_char_at()) != "]" and char is not False:
            value = self.parse_json()
            arr.append(value)

            if self.get_char_at() == ",":
                self.index += 1

        if self.get_char_at() != "]":
            if self.get_char_at() == ",":
                # Remove trailing ,
                self.remove_char_at()
            self.insert_char_at("]")

        self.index += 1
        self.context = ""
        return arr

    def parse_string(self):
        if self.get_char_at() != '"':
            self.insert_char_at('"')
        else:
            self.index += 1

        start = self.index

        # Here things get a bit heiry because a string missing a quote can also be a key in an object
        # In that case the repair action has to take into account the : separator and don't include it in the string
        while (
            (char := self.get_char_at()) != '"'
            and char is not False
            and (self.context != "object" or char != ":")
        ):
            self.index += 1

        end = self.index
        if self.get_char_at() != '"':
            self.insert_char_at('"')
        # A fallout of the previous special case, we need to update the index only if we didn't enter that case
        if self.context != "object" or char != ":":
            self.index += 1

        return self.json_str[start:end]

    def parse_number(self):
        number_pattern = r"-?\d+(\.\d+)?([eE][+-]?\d+)?"
        match = re.match(number_pattern, self.json_str[self.index :])
        if match:
            number_str = match.group()
            self.index += len(number_str)
            if "." in number_str or "e" in number_str or "E" in number_str:
                return float(number_str)
            else:
                return int(number_str)
        else:
            # This is a string then
            self.parse_string()
            # raise ValueError("Invalid number format")

    def parse_boolean_or_null(self):
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
            self.parse_string()

    def insert_char_at(self, char):
        self.json_str = self.json_str[: self.index] + char + self.json_str[self.index :]
        self.index += 1

    def get_char_at(self):
        return self.json_str[self.index] if self.index < len(self.json_str) else False

    def remove_char_at(self):
        self.json_str = self.json_str[: self.index] + self.json_str[self.index :]


def repair_json(json_str: str, return_objects: bool = False) -> any:
    parser = JSONParser(json_str.replace("\n", " ").replace("\r", " ").strip())
    parsed_json = parser.parse()
    if return_objects:
        return parsed_json
    return json.dumps(parsed_json)
