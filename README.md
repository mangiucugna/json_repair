This simple package can be used to fix an invalid JSON string. To know all cases in which this package will work, check out the [unit tests](https://github.com/mangiucugna/json_repair/tree/main/tests).

Inspired by https://github.com/josdejong/jsonrepair

# Motivation
Some LLMs are a bit iffy when it comes to returning well formed JSON data, sometimes they skip a parentheses and sometimes they add some words in it, because that's what an LLM does.
Luckily, the mistakes LLMs make are often simple enough to be fixed without destroying the content.

I searched for a lightweight python package that was able to reliably fix this problem, but couldn't find one... *so I wrote one!*

# How to use
```py
from json_repair import repair_json

good_json_string = repair_json(bad_json_string)
# If the string was super broken, this will return an empty string
```

You can use this library to completely replace `json.loads()`:

```py
import json_repair

decoded_object = json_repair.loads(json_string)
```

or just

```py
import json_repair

decoded_object = json_repair.repair_json(json_string, return_objects=True)
```

If you want to directly load in a file instead of a string, you can use `load_file`:

```py
import json_repair

decoded_object = json_repair.load_file("path/to/file.json", return_objects=True)
```

### Performance considerations
If you find this library too slow because is using `json.loads()` you can skip that by passing `skip_json_loads=True` to `repair_json`. Like:

```py
from json_repair import repair_json

good_json_string = repair_json(bad_json_string, skip_json_loads=True)
```

I made a choice of not using any fast JSON library to avoid having any external dependency, so that anybody can use it regardless of their stack.

Some rules of thumb to use:
- Setting `return_objects=True` will always be faster because the parser returns an object already and it doesn't have serialize that object to JSON
- `skip_json_loads` is faster only if you 100% know that the string is not a valid JSON
- If you are having issues with escaping pass the string as **raw** string like: `r"string with escaping\""`

## Adding to requirements
**Please pin this library only on the major version!**

We use TDD and strict semantic versioning, there will be frequent updates and no breaking changes in minor and patch versions.
To ensure that you only pin the major version of this library in your `requirements.txt`, specify the package name followed by the major version and a wildcard for minor and patch versions. For example:

```shell
json_repair==0.*
```

In this example, any version that starts with `0.` will be acceptable, allowing for updates on minor and patch versions.

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

I am sure some corner cases will be missing, if you have examples please open an issue or (*even better!*) push a PR!

# How to develop
Just create a virtual environment with `requirements.txt`, the setup uses [pre-commit](https://pre-commit.com/) to make sure all tests are run:

```shell
$ pip install virtualenv
$ python3 -m virtualenv venv
$ source venv/bin/activate
$ pip install -r requirements.txt
$ deactivate && source venv/bin/activate
```

Also confirm that the Github Actions don't fail after pushing a new commit. To manually run a pre-commit check, use:

```shell
$ pre-commit run --all-files
```

If that gives issues in your environment, you can manually run the tests with:

```shell
$ python3 -m pytest
```

# How to release
You will need owner access to this repository.
- Edit `pyproject.toml` and update the version number appropriately using `semver` notation
- **Commit and push all changes to the repository before continuing or the next steps will fail**
- Run `python -m build`
- Create a new release in Github, making sure to tag all the issues solved and contributors. Create the new tag, same as the one in the build configuration
- Once the release is created, a new Github Actions workflow will start to publish on Pypi, make sure it didn't fail

---
# Bonus Content
If you need some good Custom Instructions (System Message) to improve your chatbot responses try https://gist.github.com/mangiucugna/7ec015c4266df11be8aa510be0110fe4

---
## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=mangiucugna/json_repair&type=Date)](https://star-history.com/#mangiucugna/json_repair&Date)
