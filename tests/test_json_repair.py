from src.json_repair.json_repair import from_file, repair_json, loads


def test_repair_json():
    # Test with valid JSON strings
    assert repair_json("[]") == "[]"
    assert repair_json("[{]") == "[]"
    assert repair_json("   {  }   ") == "{}"
    assert repair_json("\"") == '""'
    assert repair_json("\n") == '""'
    assert repair_json('  {"key": true, "key2": false, "key3": null}') == '{"key": true, "key2": false, "key3": null}'
    assert repair_json('{"key": TRUE, "key2": FALSE, "key3": Null}   ') == '{"key": true, "key2": false, "key3": null}'
    assert repair_json("{'key': 'string', 'key2': false, \"key3\": null, \"key4\": unquoted}") == '{"key": "string", "key2": false, "key3": null, "key4": "unquoted"}'
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
    assert repair_json("]") == '""'
    assert repair_json("[[1\n\n]") == "[[1]]"
    assert repair_json("{") == "{}"
    assert repair_json("}") == '""'
    assert repair_json("string") == '""'
    assert repair_json("stringbeforeobject {}") == '{}'
    assert repair_json('{"') == '{}'
    assert repair_json('["') == '[]'
    assert repair_json("'\"'") == '"\\\""'
    assert repair_json("'string\"") == '"string\\\""'
    assert repair_json('{foo: [}') == '{"foo": []}'
    assert repair_json('''{ "a": "{ b": {} }" }''') == '{"a": "{ b"}'
    assert repair_json('{"key": "value:value"}') == '{"key": "value:value"}'
    assert repair_json('{“slanted_delimiter”: "value"}') == '{"slanted_delimiter": "value"}'
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
    assert (
        repair_json('{"text": "The quick brown fox won\'t jump"}')
        == '{"text": "The quick brown fox won\'t jump"}'
    )
    assert {
        repair_json('{"value_1": "value_2": "data"}') == '{"value_1": "value_2", "data": ""}'
    }
    assert {
        repair_json('{"value_1": true, COMMENT "value_2": "data"}') == '{"value_1": "value_2", "": "data"}'
    }
    # Test with garbage comments
    assert repair_json('{"value_1": true, SHOULD_NOT_EXIST "value_2": "data" AAAA }') == '{"value_1": true, "value_2": "data"}'
    assert {
        repair_json('{"" : true, "key2": "value2"}') == '{" ": true, "key2": "value_2"}'
    }
    assert {
        repair_json('{"": true, "key2": "value2"}') == '{"empty_placeholder": true, "key2": "value_2"}'
    }
    # Test a nasty corner case
    assert repair_json(' - { "test_key": ["test_value", "test_value2"] }') == '{"test_key": ["test_value", "test_value2"]}'

    #Test markdown stupidities from ChatGPT
    assert repair_json('{ "content": "[LINK]("https://google.com")" }') == '{"content": "[LINK](\\"https://google.com\\")"}'
    assert repair_json('{ "content": "[LINK](" }') == '{"content": "[LINK]("}'
    assert repair_json('{ "content": "[LINK](", "key": true }') == '{"content": "[LINK](", "key": true}'
    assert repair_json("""
                       ```json
                       { "key": "value" }
                       ```""") == '{"key": "value"}'
    assert repair_json('````{ "key": "value" }```') == '{"key": "value"}'
    assert repair_json(r'{"real_content": "Some string: Some other string Some string <a href=\"https://domain.com\">Some link</a>"') == r'{"real_content": "Some string: Some other string Some string <a href=\\\"https://domain.com\\\">Some link</a>"}'
    assert repair_json('{"key_1\n": "value"}') == '{"key_1": "value"}'
    assert repair_json('{"key\t_": "value"}') == '{"key\\t_": "value"}'
    assert repair_json('{""answer"":[{""traits"":''Female aged 60+'',""answer1"":""5""}]}') == '{"answer": [{"traits": "Female aged 60+", "answer1": "5"}]}'
    assert repair_json('{"key":""') == '{"key": ""}'
    assert repair_json('{ "words": abcdef", "numbers": 12345", "words2": ghijkl" }') == '{"words": "abcdef", "numbers": 12345, "words2": "ghijkl"}'
    assert repair_json('{"key": 1/3}') == '{"key": "1/3"}'
    assert repair_json('{"key": .25}') == '{"key": 0.25}'
    assert repair_json("""{    "a": "",    "b": [ { "c": 1} ] \n}```""") == '{"a": "", "b": [{"c": 1}]}'
    assert repair_json("Based on the information extracted, here is the filled JSON output: ```json { 'a': 'b' } ```") == '{"a": "b"}'
    assert repair_json('''{"number": 1,"reason": "According...""ans": "YES"}''') == '{"number": 1, "reason": "According...", "ans": "YES"}'
    assert repair_json('{"key": 1/3, "foo": "bar"}') == '{"key": "1/3", "foo": "bar"}'
    assert repair_json('{"here": "now", "key": 1/3, "foo": "bar"}') == '{"here": "now", "key": "1/3", "foo": "bar"}'
    assert repair_json('{"key": 12345/67890}') == '{"key": "12345/67890"}'


def test_repair_json_with_objects():
    # Test with valid JSON strings
    assert repair_json("[]", return_objects=True) == []
    assert repair_json("{}", return_objects=True) == {}
    assert repair_json('{"key": true, "key2": false, "key3": null}', return_objects=True) == {"key": True, "key2": False, "key3": None}
    assert repair_json('{"name": "John", "age": 30, "city": "New York"}', return_objects=True) == {
        "name": "John",
        "age": 30,
        "city": "New York",
    }
    assert repair_json("[1, 2, 3, 4]", return_objects=True) == [1, 2, 3, 4]
    assert repair_json('{"employees":["John", "Anna", "Peter"]} ', return_objects=True) == {
        "employees": ["John", "Anna", "Peter"]
    }

    # Test with invalid JSON strings
    assert repair_json('{"name": "John", "age": 30, "city": "New York', return_objects=True) == {
        "name": "John",
        "age": 30,
        "city": "New York",
    }
    assert repair_json('{"name": "John", "age": 30, city: "New York"}', return_objects=True) == {
        "name": "John",
        "age": 30,
        "city": "New York",
    }
    assert repair_json('{"name": "John", "age": 30, "city": New York}', return_objects=True) == {
        "name": "John",
        "age": 30,
        "city": "New York",
    }
    assert repair_json("[1, 2, 3,", return_objects=True) == [1, 2, 3]
    assert repair_json('{"employees":["John", "Anna",', return_objects=True) == {
        "employees": ["John", "Anna"]
    }

    # Test with edge cases
    assert repair_json(" ", return_objects=True) == ""
    assert repair_json("[", return_objects=True) == []
    assert repair_json("{", return_objects=True) == {}
    assert repair_json('{"key": "value:value"}', return_objects=True) == {"key": "value:value"}
    assert repair_json("{'key': 'string', 'key2': false, \"key3\": null, \"key4\": unquoted}", return_objects=True) == {"key": "string", "key2": False, "key3": None, "key4": "unquoted"}
    assert repair_json('{"name": "John", "age": 30, "city": "New', return_objects=True) == {
        "name": "John",
        "age": 30,
        "city": "New",
    }
    assert repair_json('{"employees":["John", "Anna", "Peter', return_objects=True) == {
        "employees": ["John", "Anna", "Peter"]
    }
    
    #Test with garbage comments
    assert repair_json('{"value_1": true, SHOULD_NOT_EXIST "value_2": "data" AAAA }', return_objects=True) == {'value_1': True, 'value_2': 'data'}

    #Test markdown stupidities from ChatGPT
    assert repair_json('{ "content": "[LINK]("https://google.com")" }', return_objects=True) == { "content": "[LINK](\"https://google.com\")"}
    assert repair_json('''
{
  "resourceType": "Bundle",
  "id": "1",
  "type": "collection",
  "entry": [
    {
      "resource": {
        "resourceType": "Patient",
        "id": "1",
        "name": [
          {"use": "official", "family": "Corwin", "given": ["Keisha", "Sunny"], "prefix": ["Mrs."},
          {"use": "maiden", "family": "Goodwin", "given": ["Keisha", "Sunny"], "prefix": ["Mrs."]}
        ]
      }
    }
  ]
}
''', return_objects=True) == {"resourceType": "Bundle", "id": "1", "type": "collection", "entry": [{"resource": {"resourceType": "Patient", "id": "1", "name": [{"use": "official", "family": "Corwin", "given": ["Keisha", "Sunny"], "prefix": ["Mrs."]}, {"use": "maiden", "family": "Goodwin", "given": ["Keisha", "Sunny"], "prefix": ["Mrs."]}]}}]}
    assert repair_json('{\n"html": "<h3 id="aaa">Waarom meer dan 200 Technical Experts - "Passie voor techniek"?</h3>"}', return_objects=True) == {'html': '<h3 id="aaa">Waarom meer dan 200 Technical Experts - "Passie voor techniek"?</h3>'}
    assert repair_json("""
        [
            {
                "foo": "Foo bar baz",
                "tag": "#foo-bar-baz"
            },
            {
                "foo": "foo bar "foobar" foo bar baz.",
                "tag": "#foo-bar-foobar"
            }
        ]
        """, return_objects=True) == [{"foo": "Foo bar baz", "tag": "#foo-bar-baz"},{"foo": "foo bar \"foobar\" foo bar baz.", "tag": "#foo-bar-foobar" }]


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

    # Test with numeric-like values
    assert repair_json('{"key": 10-20}') == '{"key": "10-20"}'
    assert repair_json('{"key": 1.1.1}') == '{"key": "1.1.1"}'


def test_repair_json_corner_cases_generate_by_gpt_with_objects():
    # Test with nested JSON
    assert repair_json('{"key1": {"key2": [1, 2, 3]}}', return_objects=True) == {
        "key1": {"key2": [1, 2, 3]}
    }
    assert repair_json('{"key1": {"key2": [1, 2, 3', return_objects=True) == {
        "key1": {"key2": [1, 2, 3]}
    }

    # Test with empty keys
    assert repair_json('{"": "value"}', return_objects=True) == {"": "value"}

    # Test with Unicode characters
    assert repair_json('{"key": "value\u263A"}', return_objects=True) == {"key": "value☺"}

    # Test with special characters
    assert repair_json('{"key": "value\\nvalue"}', return_objects=True) == {"key": "value\nvalue"}

    # Test with large numbers
    assert repair_json('{"key": 12345678901234567890}', return_objects=True) == {
        "key": 12345678901234567890
    }

    # Test with whitespace
    assert repair_json(' { "key" : "value" } ', return_objects=True) == {"key": "value"}

    # Test with null values
    assert repair_json('{"key": null}', return_objects=True) == {"key": None}

    # Test with numeric-like values
    assert repair_json('{"key": 10-20}', return_objects=True) == {"key": "10-20"}
    assert repair_json('{"key": 1.1.1}', return_objects=True) == {"key": "1.1.1"}


def test_repair_json_skip_json_loads():
    assert repair_json('{"key": true, "key2": false, "key3": null}', skip_json_loads=True) == '{"key": true, "key2": false, "key3": null}'
    assert repair_json('{"key": true, "key2": false, "key3": null}', return_objects=True, skip_json_loads=True) == {"key": True, "key2": False, "key3": None}
    assert repair_json('{"key": true, "key2": false, "key3": }', skip_json_loads=True) == '{"key": true, "key2": false, "key3": ""}'
    assert loads('{"key": true, "key2": false, "key3": }', skip_json_loads=True) == {"key": True, "key2": False, "key3": ""}


def test_repair_json_from_file():

    import os.path
    import pathlib
    path = pathlib.Path(__file__).parent.resolve()

    assert(from_file(os.path.join(path,"invalid.json"))) == '[{"_id": "655b66256574f09bdae8abe8", "index": 0, "guid": "31082ae3-b0f3-4406-90f4-cc450bd4379d", "isActive": false, "balance": "$2,562.78", "picture": "http://placehold.it/32x32", "age": 32, "eyeColor": "brown", "name": "Glover Rivas", "gender": "male", "company": "EMPIRICA", "email": "gloverrivas@empirica.com", "phone": "+1 (842) 507-3063", "address": "536 Montague Terrace, Jenkinsville, Kentucky, 2235", "about": "Mollit consectetur excepteur voluptate tempor dolore ullamco enim irure ullamco non enim officia. Voluptate occaecat proident laboris ea Lorem cupidatat reprehenderit nisi nisi aliqua. Amet nulla ipsum deserunt excepteur amet ad aute aute ex. Et enim minim sit veniam est quis dolor nisi sunt quis eiusmod in. Amet eiusmod cillum sunt occaecat dolor laboris voluptate in eiusmod irure aliqua duis.", "registered": "2023-11-18T09:32:36 -01:00", "latitude": 36.26102, "longitude": -91.304608, "tags": ["non", "tempor", "do", "ullamco", "dolore", "sunt", "ipsum"], "friends": [{"id": 0, "name": "Cara Shepherd"}, {"id": 1, "name": "Mason Farley"}, {"id": 2, "name": "Harriet Cochran"}], "greeting": "Hello, Glover Rivas! You have 7 unread messages.", "favoriteFruit": "strawberry"}, {"_id": "655b662585364bc57278bb6f", "index": 1, "guid": "0dea7a3a-f812-4dde-b78d-7a9b58e5da05", "isActive": true, "balance": "$1,359.48", "picture": "http://placehold.it/32x32", "age": 38, "eyeColor": "brown", "name": "Brandi Moreno", "gender": "female", "company": "MARQET", "email": "brandimoreno@marqet.com", "phone": "+1 (850) 434-2077", "address": "537 Doone Court, Waiohinu, Michigan, 3215", "about": "Irure proident adipisicing do Lorem do incididunt in laborum in eiusmod eiusmod ad elit proident. Eiusmod dolor ex magna magna occaecat. Nulla deserunt velit ex exercitation et irure sunt. Cupidatat ut excepteur ea quis labore sint cupidatat incididunt amet eu consectetur cillum ipsum proident. Occaecat exercitation aute laborum dolor proident reprehenderit laborum in voluptate culpa. Exercitation nulla adipisicing culpa aute est deserunt ea nisi deserunt consequat occaecat ut et non. Incididunt ex exercitation dolor dolor anim cillum dolore.", "registered": "2015-09-03T11:47:15 -02:00", "latitude": -19.768953, "longitude": 8.948458, "tags": ["laboris", "occaecat", "laborum", "laborum", "ex", "cillum", "occaecat"], "friends": [{"id": 0, "name": "Erna Kelly"}, {"id": 1, "name": "Black Mays"}, {"id": 2, "name": "Davis Buck"}], "greeting": "Hello, Brandi Moreno! You have 1 unread messages.", "favoriteFruit": "apple"}, {"_id": "655b6625870da431bcf5e0c2", "index": 2, "guid": "b17f6e3f-c898-4334-abbf-05cf222f143b", "isActive": false, "balance": "$1,493.77", "picture": "http://placehold.it/32x32", "age": 20, "eyeColor": "brown", "name": "Moody Meadows", "gender": "male", "company": "OPTIQUE", "email": "moodymeadows@optique.com", "phone": "+1 (993) 566-3041", "address": "766 Osborn Street, Bath, Maine, 7666", "about": "Non commodo excepteur nostrud qui adipisicing aliquip dolor minim nulla culpa proident. In ad cupidatat ea mollit ex est do deserunt proident nostrud. Cillum id id eiusmod amet exercitation nostrud cillum sunt deserunt dolore deserunt eiusmod mollit. Ut ex tempor ad laboris voluptate labore id officia fugiat exercitation amet.", "registered": "2015-01-16T02:48:28 -01:00", "latitude": -25.847327, "longitude": 63.95991, "tags": ["aute", "commodo", "adipisicing", "nostrud", "duis", "mollit", "ut"], "friends": [{"id": 0, "name": "Lacey Cash"}, {"id": 1, "name": "Gabrielle Harmon"}, {"id": 2, "name": "Ellis Lambert"}], "greeting": "Hello, Moody Meadows! You have 4 unread messages.", "favoriteFruit": "strawberry"}, {"_id": "655b6625f3e1bf422220854e", "index": 3, "guid": "92229883-2bfd-4974-a08c-1b506b372e46", "isActive": false, "balance": "$2,215.34", "picture": "http://placehold.it/32x32", "age": 22, "eyeColor": "brown", "name": "Heath Nguyen", "gender": "male", "company": "BLEENDOT", "email": "heathnguyen@bleendot.com", "phone": "+1 (989) 512-2797", "address": "135 Milton Street, Graniteville, Nebraska, 276", "about": "Consequat aliquip irure Lorem cupidatat nulla magna ullamco nulla voluptate adipisicing anim consectetur tempor aliquip. Magna aliqua nulla eu tempor esse proident. Proident fugiat ad ex Lorem reprehenderit dolor aliquip labore labore aliquip. Deserunt aute enim ea minim officia anim culpa sint commodo. Cillum consectetur excepteur aliqua exercitation Lorem veniam voluptate.", "registered": "2016-07-06T01:31:07 -02:00", "latitude": -60.997048, "longitude": -102.397885, "tags": ["do", "ad", "consequat", "irure", "tempor", "elit", "minim"], "friends": [{"id": 0, "name": "Walker Hernandez"}, {"id": 1, "name": "Maria Lane"}, {"id": 2, "name": "Mcknight Barron"}], "greeting": "Hello, Heath Nguyen! You have 4 unread messages.", "favoriteFruit": "apple"}, {"_id": "655b6625519a5b5e4b6742bf", "index": 4, "guid": "c5dc685f-6d0d-4173-b4cf-f5df29a1e8ef", "isActive": true, "balance": "$1,358.90", "picture": "http://placehold.it/32x32", "age": 33, "eyeColor": "brown", "name": "Deidre Duke", "gender": "female", "company": "OATFARM", "email": "deidreduke@oatfarm.com", "phone": "+1 (875) 587-3256", "address": "487 Schaefer Street, Wattsville, West Virginia, 4506", "about": "Laboris eu nulla esse magna sit eu deserunt non est aliqua exercitation commodo. Ad occaecat qui qui laborum dolore anim Lorem. Est qui occaecat irure enim deserunt enim aliqua ex deserunt incididunt esse. Quis in minim laboris proident non mollit. Magna ea do labore commodo. Et elit esse esse occaecat officia ipsum nisi.", "registered": "2021-09-12T04:17:08 -02:00", "latitude": 68.609781, "longitude": -87.509134, "tags": ["mollit", "cupidatat", "irure", "sit", "consequat", "anim", "fugiat"], "friends": [{"id": 0, "name": "Bean Paul"}, {"id": 1, "name": "Cochran Hubbard"}, {"id": 2, "name": "Rodgers Atkinson"}], "greeting": "Hello, Deidre Duke! You have 6 unread messages.", "favoriteFruit": "apple"}, {"_id": "655b6625a19b3f7e5f82f0ea", "index": 5, "guid": "75f3c264-baa1-47a0-b21c-4edac23d9935", "isActive": true, "balance": "$3,554.36", "picture": "http://placehold.it/32x32", "age": 26, "eyeColor": "blue", "name": "Lydia Holland", "gender": "female", "company": "ESCENTA", "email": "lydiaholland@escenta.com", "phone": "+1 (927) 482-3436", "address": "554 Rockaway Parkway, Kohatk, Montana, 6316", "about": "Consectetur ea est labore commodo laborum mollit pariatur non enim. Est dolore et non laboris tempor. Ea incididunt ut adipisicing cillum labore officia tempor eiusmod commodo. Cillum fugiat ex consectetur ut nostrud anim nostrud exercitation ut duis in ea. Eu et id fugiat est duis eiusmod ullamco quis officia minim sint ea nisi in.", "registered": "2018-03-13T01:48:56 -01:00", "latitude": -88.495799, "longitude": 71.840667, "tags": ["veniam", "minim", "consequat", "consequat", "incididunt", "consequat", "elit"], "friends": [{"id": 0, "name": "Debra Massey"}, {"id": 1, "name": "Weiss Savage"}, {"id": 2, "name": "Shannon Guerra"}], "greeting": "Hello, Lydia Holland! You have 5 unread messages.", "favoriteFruit": "banana"}]'
