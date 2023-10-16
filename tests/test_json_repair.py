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
    assert repair_json("[[1\n\n]") == "[[1]]"
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
    assert (
        repair_json('{"employees":["John", "Anna", "Peter"]}')
        == '{"employees": ["John", "Anna", "Peter"]}'
    )
    assert (
        repair_json('{"text": "The quick brown fox,"}')
        == '{"text": "The quick brown fox,"}'
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


def test_repair_json_corner_cases_generate_by_gpt():
    # Test with nested JSON
    assert (
        repair_json('{"key1": {"key2": [1, 2, 3]}}') == '{"key1": {"key2": [1, 2, 3]}}'
    )
    assert repair_json('{"key1": {"key2": [1, 2, 3') == '{"key1": {"key2": [1, 2, 3]}}'

    # Test with empty keys
    assert repair_json('{"": "value"}') == '{"": "value"}'

    # Test with Unicode characters
    assert repair_json('{"key": "value\u263A"}') == '{"key": "value\\u263a"}'

    # Test with special characters
    assert repair_json('{"key": "value\\nvalue"}') == '{"key": "value\\nvalue"}'

    # Test with large numbers
    assert (
        repair_json('{"key": 12345678901234567890}') == '{"key": 12345678901234567890}'
    )

    # Test with whitespace
    assert repair_json(' { "key" : "value" } ') == '{"key": "value"}'

    # Test with null values
    assert repair_json('{"key": null}') == '{"key": null}'


def test_repair_json_corner_cases_generate_by_gpt_with_objects():
    # Test with nested JSON
    assert repair_json('{"key1": {"key2": [1, 2, 3]}}', True) == {
        "key1": {"key2": [1, 2, 3]}
    }
    assert repair_json('{"key1": {"key2": [1, 2, 3', True) == {
        "key1": {"key2": [1, 2, 3]}
    }

    # Test with empty keys
    assert repair_json('{"": "value"}', True) == {"": "value"}

    # Test with Unicode characters
    assert repair_json('{"key": "value\u263A"}', True) == {"key": "value☺"}

    # Test with special characters
    assert repair_json('{"key": "value\\nvalue"}', True) == {"key": "value\nvalue"}

    # Test with large numbers
    assert repair_json('{"key": 12345678901234567890}', True) == {
        "key": 12345678901234567890
    }

    # Test with whitespace
    assert repair_json(' { "key" : "value" } ', True) == {"key": "value"}

    # Test with null values
    assert repair_json('{"key": null}', True) == {"key": None}

def test_functions_output():
    assert repair_json("""{
    "path": "/Users/david/local-git/twitter_poster/db/db_methods.py",
    "contents": "import pandas as pd
from datetime import datetime 
from sqlalchemy import create_engine
from twitter_poster.modules.utils import date_to_str, str_to_date

engine = create_engine('sqlite:///twitter_poster.db')

def get_post (date: datetime) -> dict:
    date_str = date_to_str (date)
    with engine.connect() as connection:
        result = connection.execute(f\"SELECT * FROM posts WHERE send_date='{date_str}'\")
    post = result. fetchone ()
    if post:
        return f'id': postI0], 'tweet_id': post[1], 'content': post[2], 'send_date': str_to_date(post[3]), 'was_sent': post[4]}
    else:
        return {}

def index_posts(start_date: datetime, end_date: datetime) → list:
    start_date_str = date_to_str(start_date)
    end_date_str = date_to_str (end_date)
    with engine.connect) as connection:
        result = connection.execute(f\"SELECT * FROM posts WHERE send_date BETWEEN '{start_date_str}' AND '{end_date_str}'\")
    posts = result. fetchall)
    return [{'id': post[0], "tweet_id': post[1], 'content': post[21, 'send_date': str_to_date(post[31), 'was_sent': post[4]} for post in posts]"
}""") == """{"path": "/Users/david/local-git/twitter_poster/db/db_methods.py", "contents": "import pandas as pd\\nfrom datetime import datetime \\nfrom sqlalchemy import create_engine\\nfrom twitter_poster.modules.utils import date_to_str, str_to_date\\n\\nengine = create_engine('sqlite:///twitter_poster.db')\\n\\ndef get_post (date: datetime) -> dict:\\n    date_str = date_to_str (date)\\n    with engine.connect() as connection:\\n        result = connection.execute(f", "SELECT * FROM posts WHERE send_date='{date_str}'": "post = result. fetchone ()\\n    if post:\\n        return f'id': postI0]", "'tweet_id'": "post[1]", "'content'": "post[2]", "'send_date'": "str_to_date(post[3])", "'was_sent'": "post[4]"}"""
    assert repair_json("""{
    "path": "/Users/david/local-git/twitter_poster/db/db_methods.py",
    "contents": "import pandas as pd
from datetime import datetime 
from sqlalchemy import create_engine
from twitter_poster.modules.utils import date_to_str, str_to_date

engine = create_engine('sqlite:///twitter_poster.db')

def get_post (date: datetime) -> dict:
    date_str = date_to_str (date)
    with engine.connect() as connection:
        result = connection.execute(f\"SELECT * FROM posts WHERE send_date='{date_str}'\")
    post = result. fetchone ()
    if post:
        return f'id': postI0], 'tweet_id': post[1], 'content': post[2], 'send_date': str_to_date(post[3]), 'was_sent': post[4]}
    else:
        return {}

def index_posts(start_date: datetime, end_date: datetime) → list:
    start_date_str = date_to_str(start_date)
    end_date_str = date_to_str (end_date)
    with engine.connect) as connection:
        result = connection.execute(f\"SELECT * FROM posts WHERE send_date BETWEEN '{start_date_str}' AND '{end_date_str}'\")
    posts = result. fetchall)
    return [{'id': post[0], "tweet_id': post[1], 'content': post[21, 'send_date': str_to_date(post[31), 'was_sent': post[4]} for post in posts]"
}""", True) == {"path": "/Users/david/local-git/twitter_poster/db/db_methods.py", "contents": "import pandas as pd\nfrom datetime import datetime \nfrom sqlalchemy import create_engine\nfrom twitter_poster.modules.utils import date_to_str, str_to_date\n\nengine = create_engine('sqlite:///twitter_poster.db')\n\ndef get_post (date: datetime) -> dict:\n    date_str = date_to_str (date)\n    with engine.connect() as connection:\n        result = connection.execute(f", "SELECT * FROM posts WHERE send_date='{date_str}'": "post = result. fetchone ()\n    if post:\n        return f'id': postI0]", "'tweet_id'": "post[1]", "'content'": "post[2]", "'send_date'": "str_to_date(post[3])", "'was_sent'": "post[4]"}