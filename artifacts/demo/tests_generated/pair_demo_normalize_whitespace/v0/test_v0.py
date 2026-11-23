from examples import normalize_whitespace

def test_normalize():
    assert normalize_whitespace("  a   b ") == "a b"
    assert normalize_whitespace("") == ""
