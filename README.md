This simple package can be used to repair a broken json file. To know all cases in which this package will work, check out the unit test.

Inspired by https://github.com/josdejong/jsonrepair with contributions by GPT-4

# Motivation
I was using GPT a lot and there is no sure fire way to get structured output out of it.
You can ask for a JSON output or use the Functions paradigm, either way the documentation from OpenAI clearly states that it might not return a valid JSON.
Luckily, the mistakes GPT makes are simple enough to be fixed without destroying the content.
I searched for a lightweight python package but couldn't find any.

So I wrote this one.

You can look how I used it by checking out this demo: https://huggingface.co/spaces/mangiucugna/difficult-conversations-bot/

# How to use
    from json_repair import repair_json
    good_json_string = repair_json(bad_json_string)

# How it works
This module will parse the JSON file following the BNF definition:

    <json> ::= <primitive> | <container>

    <primitive> ::= <number> | <string> | <boolean>
    ; Where:
    ; <number> is a valid real number expressed in one of a number of given formats
    ; <string> is a string of valid characters enclosed in quotes
    ; <boolean> is one of the literal strings 'true', 'false', or 'null' (unquoted)

    <container> ::= <object> | <array>
    <array> ::= '[' [ <json> *(', ' <json>) ] ']' ; A sequence of JSON values separated by commas
    <object> ::= '{' [ <member> *(', ' <member>) ] '}' ; A sequence of 'members'
    <member> ::= <string> ': ' <json> ; A pair consisting of a name, and a JSON value

If something is wrong (a missing parantheses or quotes for example) it will use a few simple heuristics to fix the JSON string:
- Add the missing parentheses if the parser believes that the array or object should be closed
- Quote strings or add missing single quotes
- Adjust whitespaces and remove line breaks

I am sure some corner cases will be missing, if you have examples please open an issue or even better push a PR

# How to develop
Just create a virtual environment with `requirements.txt`, the setup uses pre-commit to make sure all tests are run

# How to release
You will need owner access to this repository
- Edit `pyproject.toml` and update the version number appropriately using `semver` notation
- Run `python -m build`
- **Commit and push all changes to the repository before continuing or the next steps will fail**
- Create a new release in Github, making sure to tag all the issues solved and contributors. Create the new tag, same as the one in the build configuration
- Once the release is created, a new Github Actions workflow will start to publish on Pypi, make sure it didn't fail

---
# Bonus Content
If you need some good Custom Instructions (System Message) to improve your chatbot responses try https://gist.github.com/mangiucugna/7ec015c4266df11be8aa510be0110fe4
