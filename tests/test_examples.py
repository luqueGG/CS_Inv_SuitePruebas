from ar_pilot.examples import list_functions, get_function

def test_list_functions():
    fs = list_functions()
    assert len(fs) == 8

def test_examples_basic():
    assert get_function("normalize_whitespace")("  a   b ") == "a b"
    assert get_function("clamp")(5, 0, 10) == 5