from src.json_repair import load_file

def test_load_file():
    # Test load_file with a valid JSON file
    dataOne = load_file("tests/json/valid.json", return_objects=True)
    assert type(dataOne) == list

    # Test load_file with an invalid JSON file
    dataTwo = load_file("tests/json/invalid.json", return_objects=True)
    assert type(dataTwo) == list

    # Assert that the data returned from the invalid JSON file is the same as the data in the valid file
    assert dataTwo == dataOne
