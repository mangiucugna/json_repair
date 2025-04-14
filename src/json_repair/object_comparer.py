from typing import Any


class ObjectComparer:
    def __init__(self) -> None:
        return

    @staticmethod
    def is_same_object(obj1: Any, obj2: Any, path: str = "") -> bool:
        """
        Recursively compares two objects and ensures that:
        - Their types match
        - Their keys/structure match
        """
        if type(obj1) is not type(obj2):
            # Fail immediately if the types don't match
            return False

        if isinstance(obj1, dict) and isinstance(obj2, dict):
            # Compare dictionary keys
            keys1, keys2 = set(obj1.keys()), set(obj2.keys())
            common_keys = keys1 & keys2
            extra_keys1 = keys1 - keys2
            extra_keys2 = keys2 - keys1

            if extra_keys1:
                return False
            if extra_keys2:
                return False

            # Recursively compare the common keys
            for key in common_keys:
                if not ObjectComparer.is_same_object(
                    obj1[key], obj2[key], path=f"{path}/{key}"
                ):
                    return False

        elif isinstance(obj1, list) and isinstance(obj2, list):
            # Compare lists
            min_length = min(len(obj1), len(obj2))
            if len(obj1) != len(obj2):
                return False

            for i in range(min_length):
                if not ObjectComparer.is_same_object(
                    obj1[i], obj2[i], path=f"{path}[{i}]"
                ):
                    return False

            if len(obj1) > len(obj2):
                return False
            elif len(obj2) > len(obj1):
                return False

        return True
