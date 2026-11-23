from examples import normalize_whitespace

def test_normalize_basic():
    assert normalize_whitespace("  a   b ") == "a b", "basic collapse"

def test_normalize_empty():
    assert normalize_whitespace("") == "", "empty input"