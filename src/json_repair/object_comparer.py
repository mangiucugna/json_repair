from typing import Any


class ObjectComparer:  # pragma: no cover
    def __init__(self) -> None:
        pass  # No operation performed in the constructor

    @staticmethod
    def is_same_object(obj1: Any, obj2: Any) -> bool:
        """
        Recursively compares two objects and ensures that:
        - Their types match
        - Their keys/structure match
        """
        if type(obj1) is not type(obj2):
            # Fail immediately if the types don't match
            return False

        if isinstance(obj1, dict):
            # Quick length check before key compares
            if len(obj1) != len(obj2):
                return False
            for key in obj1:
                if key not in obj2:
                    return False
                if not ObjectComparer.is_same_object(obj1[key], obj2[key]):
                    return False
            return True

        elif isinstance(obj1, list):
            if len(obj1) != len(obj2):
                return False
            return all(ObjectComparer.is_same_object(obj1[i], obj2[i]) for i in range(len(obj1)))

        # For atoms: types already match, so just return True
        return True
