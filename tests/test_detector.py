import textwrap
from ar_pilot.detector import analyze_source


def test_zero_asserts():
    src = "def test_x():\n    pass\n"
    r = analyze_source(src, "t.py")
    assert r.status == "ok"
    assert r.ar_flagged_tests == 0
    assert r.ar_total_asserts == 0


def test_one_unlabeled():
    src = "def test_x():\n    assert 1 == 1\n"
    r = analyze_source(src, "t.py")
    assert r.ar_flagged_tests == 0
    assert r.ar_unlabeled_asserts == 1


def test_two_unlabeled_candidate():
    src = "def test_x():\n    assert 1 == 1\n    assert 2 == 2\n"
    r = analyze_source(src, "t.py")
    assert r.ar_flagged_tests == 1
    assert r.ar_unlabeled_asserts == 2
    assert r.tests[0].ar_candidate is True


def test_two_labeled_not_candidate():
    src = 'def test_x():\n    assert 1 == 1, "a"\n    assert 2 == 2, "b"\n'
    r = analyze_source(src, "t.py")
    assert r.ar_flagged_tests == 0
    assert r.ar_unlabeled_asserts == 0
    assert r.ar_total_asserts == 2


def test_mixed():
    src = 'def test_x():\n    assert 1 == 1\n    assert 2 == 2, "msg"\n'
    r = analyze_source(src, "t.py")
    assert r.ar_flagged_tests == 0
    assert r.ar_unlabeled_asserts == 1


def test_multiple_functions():
    src = textwrap.dedent("""
    def test_a():
        assert 1 == 1
        assert 2 == 2

    def test_b():
        assert 3 == 3
    """)
    r = analyze_source(src, "t.py")
    assert len(r.tests) == 2
    assert r.ar_flagged_tests == 1


def test_method_in_test_class():
    src = textwrap.dedent("""
    class TestFoo:
        def test_bar(self):
            assert 1 == 1
            assert 2 == 2
    """)
    r = analyze_source(src, "t.py")
    assert len(r.tests) == 1
    assert r.tests[0].name == "test_bar"
    assert r.ar_flagged_tests == 1


def test_nested_function_not_counted():
    src = textwrap.dedent("""
    def test_outer():
        assert 1 == 1
        def inner():
            assert 2 == 2
            assert 3 == 3
        assert 4 == 4
    """)
    r = analyze_source(src, "t.py")
    assert r.tests[0].total_asserts == 2
    assert r.tests[0].ar_candidate is True


def test_syntax_error():
    src = "def test_x(\n"
    r = analyze_source(src, "t.py")
    assert r.status == "parse_error"
    assert r.tests == []


def test_pytest_raises_not_counted_as_assert():
    src = textwrap.dedent("""
    import pytest
    def test_x():
        with pytest.raises(ValueError):
            foo()
        assert 1 == 1
        assert 2 == 2
    """)
    r = analyze_source(src, "t.py")
    # pytest.raises is not ast.Assert; only 2 asserts
    assert r.tests[0].total_asserts == 2
    assert r.ar_flagged_tests == 1


def test_line_numbers():
    src = "def test_x():\n    assert 1 == 1\n    assert 2 == 2\n"
    r = analyze_source(src, "t.py")
    lines = [a["line"] for a in r.tests[0].asserts]
    assert lines == [2, 3]