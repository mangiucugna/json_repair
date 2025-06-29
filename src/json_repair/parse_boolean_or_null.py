def parse_boolean_or_null(self) -> bool | str | None:
    # <boolean> is one of the literal strings 'true', 'false', or 'null' (unquoted)
    starting_index = self.index
    char = (self.get_char_at() or "").lower()
    value: tuple[str, bool | None] | None = None
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
