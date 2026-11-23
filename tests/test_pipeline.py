from ar_pilot.experiment import extract_code

def test_extract_code_fence():
    text = "here\n```python\ndef test_x():\n    assert 1 == 1\n```\n"
    assert "def test_x" in extract_code(text)

def test_extract_code_no_fence():
    assert extract_code("def test_x(): pass") == "def test_x(): pass\n"