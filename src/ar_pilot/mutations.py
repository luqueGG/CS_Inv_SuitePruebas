"""Helpers for mutation evaluation naming/paths."""

from __future__ import annotations

from pathlib import Path


def artifact_dir(base: Path, run_id: str) -> Path:
    d = base / run_id
    d.mkdir(parents=True, exist_ok=True)
    return d
