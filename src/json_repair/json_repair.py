"""
This module will parse the JSON file following the BNF definition:

    <json> ::= <container>

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

All supported use cases are in the unit tests
"""

import argparse
import sys
import json
from typing import Dict, List, Optional, Union, TextIO, Tuple
from .json_parser import JSONParser, JSONReturnType


def repair_json(
    json_str: str = "",
    return_objects: bool = False,
    skip_json_loads: bool = False,
    logging: bool = False,
    json_fd: Optional[TextIO] = None,
    ensure_ascii: bool = True,
    chunk_length: int = 0,
) -> Union[JSONReturnType, Tuple[JSONReturnType, List[Dict[str, str]]]]:
    """
    Given a json formatted string, it will try to decode it and, if it fails, it will try to fix it.
    It will return the fixed string by default.
    When `return_objects=True` is passed, it will return the decoded data structure instead.
    When `skip_json_loads=True` is passed, it will not call the built-in json.loads() function
    When `logging=True` is passed, it will return a tuple with the repaired json and a log of all repair actions
    """
    parser = JSONParser(json_str, json_fd, logging, chunk_length)
    if skip_json_loads:
        parsed_json = parser.parse()
    else:
        try:
            if json_fd:
                parsed_json = json.load(json_fd)
            else:
                parsed_json = json.loads(json_str)
        except json.JSONDecodeError:
            parsed_json = parser.parse()
    # It's useful to return the actual object instead of the json string,
    # it allows this lib to be a replacement of the json library
    if return_objects or logging:
        return parsed_json
    return json.dumps(parsed_json, ensure_ascii=ensure_ascii)


def loads(
    json_str: str,
    skip_json_loads: bool = False,
    logging: bool = False,
) -> Union[JSONReturnType, Tuple[JSONReturnType, List[Dict[str, str]]]]:
    """
    This function works like `json.loads()` except that it will fix your JSON in the process.
    It is a wrapper around the `repair_json()` function with `return_objects=True`.
    """
    return repair_json(
        json_str=json_str,
        return_objects=True,
        skip_json_loads=skip_json_loads,
        logging=logging,
    )


def load(
    fd: TextIO,
    skip_json_loads: bool = False,
    logging: bool = False,
    chunk_length: int = 0,
) -> Union[JSONReturnType, Tuple[JSONReturnType, List[Dict[str, str]]]]:
    """
    This function works like `json.load()` except that it will fix your JSON in the process.
    It is a wrapper around the `repair_json()` function with `json_fd=fd` and `return_objects=True`.
    """
    return repair_json(
        json_fd=fd,
        chunk_length=chunk_length,
        return_objects=True,
        skip_json_loads=skip_json_loads,
        logging=logging,
    )


def from_file(
    filename: str,
    skip_json_loads: bool = False,
    logging: bool = False,
    chunk_length: int = 0,
) -> Union[JSONReturnType, Tuple[JSONReturnType, List[Dict[str, str]]]]:
    """
    This function is a wrapper around `load()` so you can pass the filename as string
    """
    fd = open(filename)
    jsonobj = load(
        fd=fd,
        skip_json_loads=skip_json_loads,
        logging=logging,
        chunk_length=chunk_length,
    )
    fd.close()

    return jsonobj


def cli(inline_args: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Repair and parse JSON files.")
    parser.add_argument("filename", help="The JSON file to repair")
    parser.add_argument(
        "-i",
        "--inline",
        action="store_true",
        help="Replace the file inline instead of returning the output to stdout",
    )
    parser.add_argument(
        "-o",
        "--output",
        metavar="TARGET",
        help="If specified, the output will be written to TARGET filename instead of stdout",
    )
    parser.add_argument(
        "--ensure_ascii",
        action="store_true",
        help="Pass ensure_ascii=True to json.dumps()",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        help="Number of spaces for indentation (Default 2)",
    )

    if inline_args is None:  # pragma: no cover
        args = parser.parse_args()
    else:
        args = parser.parse_args(
            inline_args
        )  # This is needed so this function is testable

    if args.inline and args.output:  # pragma: no cover
        print("Error: You cannot pass both --inline and --output", file=sys.stderr)
        sys.exit(1)

    ensure_ascii = False
    if args.ensure_ascii:
        ensure_ascii = True

    try:
        result = from_file(args.filename)

        if args.inline or args.output:
            fd = open(args.output or args.filename, mode="w")
            json.dump(result, fd, indent=args.indent, ensure_ascii=ensure_ascii)
            fd.close()
        else:
            print(json.dumps(result, indent=args.indent, ensure_ascii=ensure_ascii))
    except Exception as e:  # pragma: no cover
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)

    return 0  # Success


if __name__ == "__main__":  # pragma: no cover
    sys.exit(cli())
