"""Pilot functions under test: pure, deterministic, well-specified."""

from __future__ import annotations

import math
import re


def normalize_whitespace(text: str) -> str:
    """Collapse runs of whitespace to a single space and strip ends.

    >>> normalize_whitespace("  a   b\\tc\\n")
    'a b c'
    >>> normalize_whitespace("")
    ''
    """
    return " ".join(text.split())


def is_palindrome(text: str) -> bool:
    """Case-insensitive palindrome check ignoring non-alphanumerics.

    >>> is_palindrome("A man, a plan, a canal: Panama")
    True
    >>> is_palindrome("race a car")
    False
    """
    cleaned = re.sub(r"[^a-z0-9]", "", text.lower())
    return cleaned == cleaned[::-1]


def clamp(value: float, lo: float, hi: float) -> float:
    """Clamp value to [lo, hi]. Requires lo <= hi.

    >>> clamp(5, 0, 10)
    5
    >>> clamp(-3, 0, 10)
    0
    >>> clamp(15, 0, 10)
    10
    """
    if lo > hi:
        raise ValueError("lo must be <= hi")
    return max(lo, min(hi, value))


def discount(price: float, percent: float) -> float:
    """Apply percent discount to price. percent in [0, 100].

    >>> discount(100.0, 10.0)
    90.0
    >>> discount(50.0, 0.0)
    50.0
    """
    if price < 0:
        raise ValueError("price must be >= 0")
    if not (0 <= percent <= 100):
        raise ValueError("percent must be in [0, 100]")
    return round(price * (1 - percent / 100.0), 2)


def median(values: list[float]) -> float:
    """Median of a non-empty list.

    >>> median([1, 2, 3])
    2.0
    >>> median([1, 2, 3, 4])
    2.5
    """
    if not values:
        raise ValueError("values must be non-empty")
    s = sorted(values)
    n = len(s)
    mid = n // 2
    if n % 2:
        return float(s[mid])
    return (s[mid - 1] + s[mid]) / 2.0


def slugify(text: str) -> str:
    """Convert text to URL-friendly slug (lowercase, hyphenated).

    >>> slugify("Hello, World!")
    'hello-world'
    >>> slugify("  multiple   spaces  ")
    'multiple-spaces'
    """
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def parse_int_list(s: str) -> list[int]:
    """Parse comma-separated integers, ignoring empty tokens.

    >>> parse_int_list("1, 2,3,,4")
    [1, 2, 3, 4]
    >>> parse_int_list("")
    []
    """
    out: list[int] = []
    for token in s.split(","):
        token = token.strip()
        if token == "":
            continue
        out.append(int(token))
    return out


def safe_divide(a: float, b: float) -> float:
    """Divide a by b; raise ZeroDivisionError if b == 0.

    >>> safe_divide(10, 2)
    5.0
    >>> safe_divide(1, 0)
    Traceback (most recent call last):
        ...
    ZeroDivisionError
    """
    if b == 0:
        raise ZeroDivisionError("division by zero")
    return a / b


FUNCTIONS = [
    "normalize_whitespace",
    "is_palindrome",
    "clamp",
    "discount",
    "median",
    "slugify",
    "parse_int_list",
    "safe_divide",
]


def get_function(name: str):
    import importlib
    mod = importlib.import_module(__name__)
    return getattr(mod, name)


def list_functions():
    return list(FUNCTIONS)
