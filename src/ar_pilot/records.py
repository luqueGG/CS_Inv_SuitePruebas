"""Structured run records (CSV/JSON/JSONL/manifest)."""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CSV_FIELDS = [
    "run_id", "pair_id", "function_id", "condition", "stage", "model", "temperature",
    "max_tokens", "prompt_sha256", "source_sha256", "test_sha256", "pytest_status",
    "pytest_passed", "pytest_failed", "pytest_errors", "ar_flagged_tests",
    "ar_unlabeled_asserts", "ar_total_asserts", "mutants_killed", "mutants_survived",
    "mutants_other", "mutation_score", "mutation_status", "elapsed_seconds", "artifact_dir",
]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


@dataclass
class RunRecord:
    run_id: str
    pair_id: str
    function_id: str
    condition: str  # v0 | generic | ar_specific
    stage: str  # generated | revised | evaluated
    model: str
    temperature: float
    max_tokens: int
    prompt_sha256: str
    source_sha256: str
    test_sha256: str
    pytest_status: str | None = None
    pytest_passed: int | None = None
    pytest_failed: int | None = None
    pytest_errors: int | None = None
    ar_flagged_tests: int | None = None
    ar_unlabeled_asserts: int | None = None
    ar_total_asserts: int | None = None
    mutants_killed: int | None = None
    mutants_survived: int | None = None
    mutants_other: int | None = None
    mutation_score: float | None = None
    mutation_status: str | None = None
    elapsed_seconds: float | None = None
    artifact_dir: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


def write_csv(path: Path, records: list[RunRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        for r in records:
            d = asdict(r)
            # flatten extra into row? keep known fields only
            row = {k: d.get(k) for k in CSV_FIELDS}
            w.writerow(row)


def append_jsonl(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
