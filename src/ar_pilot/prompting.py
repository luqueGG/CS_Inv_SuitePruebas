"""Prompt loading and rendering."""

from __future__ import annotations

import hashlib
from pathlib import Path


def load_prompt(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def render(template: str, **kwargs) -> str:
    # Simple {key} substitution without touching braces in code.
    out = template
    for k, v in kwargs.items():
        out = out.replace("{" + k + "}", str(v))
    return out


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
