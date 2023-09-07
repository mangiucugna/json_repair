from src.json_repair.json_repair import repair_json


def test_repair_json():
    # Test with valid JSON strings
    assert repair_json("[]") == "[]"
    assert repair_json("{}") == "{}"
    assert (
        repair_json('{"name": "John", "age": 30, "city": "New York"}')
        == '{"name": "John", "age": 30, "city": "New York"}'
    )
    assert repair_json("[1, 2, 3, 4]") == "[1, 2, 3, 4]"
    assert (
        repair_json('{"employees":["John", "Anna", "Peter"]} ')
        == '{"employees": ["John", "Anna", "Peter"]}'
    )

    # Test with invalid JSON strings
    assert (
        repair_json('{"name": "John", "age": 30, "city": "New York')
        == '{"name": "John", "age": 30, "city": "New York"}'
    )
    assert (
        repair_json('{"name": "John", "age": 30, city: "New York"}')
        == '{"name": "John", "age": 30, "city": "New York"}'
    )
    assert (
        repair_json('{"name": "John", "age": 30, "city": New York}')
        == '{"name": "John", "age": 30, "city": "New York"}'
    )
    assert (
        repair_json('{"name": John, "age": 30, "city": "New York"}')
        == '{"name": "John", "age": 30, "city": "New York"}'
    )
    assert repair_json("[1, 2, 3,") == "[1, 2, 3]"
    assert (
        repair_json('{"employees":["John", "Anna",')
        == '{"employees": ["John", "Anna"]}'
    )

    # Test with edge cases
    assert repair_json(" ") == '""'
    assert repair_json("[") == "[]"
    assert repair_json("{") == "{}"
    assert repair_json('{"key": "value:value"}') == '{"key": "value:value"}'
    assert (
        repair_json('{"name": "John", "age": 30, "city": "New')
        == '{"name": "John", "age": 30, "city": "New"}'
    )
    assert (
        repair_json('{"employees":["John", "Anna", "Peter')
        == '{"employees": ["John", "Anna", "Peter"]}'
    )


def test_repair_json_with_objects():
    # Test with valid JSON strings
    assert repair_json("[]", True) == []
    assert repair_json("{}", True) == {}
    assert repair_json('{"name": "John", "age": 30, "city": "New York"}', True) == {
        "name": "John",
        "age": 30,
        "city": "New York",
    }
    assert repair_json("[1, 2, 3, 4]", True) == [1, 2, 3, 4]
    assert repair_json('{"employees":["John", "Anna", "Peter"]} ', True) == {
        "employees": ["John", "Anna", "Peter"]
    }

    # Test with invalid JSON strings
    assert repair_json('{"name": "John", "age": 30, "city": "New York', True) == {
        "name": "John",
        "age": 30,
        "city": "New York",
    }
    assert repair_json('{"name": "John", "age": 30, city: "New York"}', True) == {
        "name": "John",
        "age": 30,
        "city": "New York",
    }
    assert repair_json('{"name": "John", "age": 30, "city": New York}', True) == {
        "name": "John",
        "age": 30,
        "city": "New York",
    }
    assert repair_json("[1, 2, 3,", True) == [1, 2, 3]
    assert repair_json('{"employees":["John", "Anna",', True) == {
        "employees": ["John", "Anna"]
    }

    # Test with edge cases
    assert repair_json(" ", True) == ""
    assert repair_json("[", True) == []
    assert repair_json("{", True) == {}
    assert repair_json('{"key": "value:value"}', True) == {"key": "value:value"}
    assert repair_json('{"name": "John", "age": 30, "city": "New', True) == {
        "name": "John",
        "age": 30,
        "city": "New",
    }
    assert repair_json('{"employees":["John", "Anna", "Peter', True) == {
        "employees": ["John", "Anna", "Peter"]
    }
