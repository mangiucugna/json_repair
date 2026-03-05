from src.json_repair.utils.pattern_properties import match_pattern_properties


def test_match_pattern_properties_exact_anchor_contains():
    pattern_properties = {
        "^abc$": {"name": "exact"},
        "bc": {"name": "contains"},
    }

    matched, unsupported = match_pattern_properties(pattern_properties, "abc")

    assert matched == [{"name": "exact"}, {"name": "contains"}]
    assert unsupported == []


def test_match_pattern_properties_marks_unsupported_regex_patterns():
    pattern_properties = {
        "^x[0-9]+$": {"name": "unsupported"},
        "^x": {"name": "supported"},
    }

    matched, unsupported = match_pattern_properties(pattern_properties, "x1")

    assert matched == [{"name": "supported"}]
    assert unsupported == ["^x[0-9]+$"]
