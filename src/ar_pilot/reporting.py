"""Generate human-readable documentation for a run output directory."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def generate(output_dir: str | Path) -> list[Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    runs = _read_csv(out / "runs.csv")
    manifest = _read_json(out / "manifest.json")
    created: list[Path] = []

    # README.md (proposal 8)
    readme = out / "README.md"
    readme.write_text(
        "# Run output\n\n"
        f"- Directory: `{out}`\n"
        f"- Mode: {manifest.get('mode', 'unknown')}\n"
        f"- Real or synthetic: {manifest.get('real_or_synthetic', 'unknown')}\n"
        f"- Model: {manifest.get('model', 'n/a')}\n"
        f"- Provider: {manifest.get('provider', 'n/a')}\n"
        f"- Functions: {', '.join(manifest.get('functions', [])) or 'n/a'}\n"
        f"- Pairs: {manifest.get('pairs', 'n/a')}\n"
        f"- Generated at (UTC): {manifest.get('generated_at_utc', 'n/a')}\n\n"
        "## Contents\n"
        "- `runs.csv`: one row per evaluated version.\n"
        "- `generations.jsonl`: prompts/responses/hashes per version.\n"
        "- `manifest.json`: run configuration and provenance.\n"
        "- `tests_generated/`: generated test files (immutable by convention).\n"
        "- `pytest_logs/`, `mutation_logs/`: raw tool output.\n\n"
        "## Reproduce\n"
        f"- Re-run: `python -m ar_pilot.cli run --config configs/pilot.json --output {out}`\n"
        "- Tests: `python -m pytest -q`\n\n"
        "## Interpretation\n"
        "Descriptive only. `mutation_score = killed/(killed+survived)*100` when baseline passes and denominator>0; "
        "otherwise `null` with `mutation_status`. No causal/statistical claims.\n",
        encoding="utf-8",
    )
    created.append(readme)

    # summary.md (proposal 1)
    n_funcs = len({r.get("function_id") for r in runs}) if runs else 0
    n_rows = len(runs)
    scores = [r.get("mutation_score") for r in runs if r.get("mutation_score") not in (None, "", "None")]
    avg_score = (sum(float(x) for x in scores) / len(scores)) if scores else None
    summary = out / "summary.md"
    summary.write_text(
        "# Summary\n\n"
        f"- Generated at (UTC): {datetime.now(timezone.utc).isoformat()}\n"
        f"- Functions: {n_funcs}\n"
        f"- Evaluated versions (rows): {n_rows}\n"
        f"- Average mutation score (where available): "
        f"{'{:.2f}'.format(avg_score) if avg_score is not None else 'n/a'}\n\n"
        "## By condition\n"
        + _condition_table(runs)
        + "\n## Artifacts\n"
        + "- `runs.csv`, `generations.jsonl`, `manifest.json`\n"
        + "- `tests_generated/`, `pytest_logs/`, `mutation_logs/`\n",
        encoding="utf-8",
    )
    created.append(summary)

    # comparison.md (proposal 4)
    comparison = out / "comparison.md"
    comparison.write_text(
        "# Comparison (v0 vs generic vs ar_specific)\n\n" + _comparison_table(runs) + "\n",
        encoding="utf-8",
    )
    created.append(comparison)

    # notes.md (proposal 7)
    notes = out / "notes.md"
    notes.write_text(
        "# Notes and deviations\n\n" + _notes(runs, manifest) + "\n",
        encoding="utf-8",
    )
    created.append(notes)

    return created


def _condition_table(runs: list[dict[str, str]]) -> str:
    from collections import defaultdict

    agg: dict[str, dict[str, int]] = defaultdict(lambda: {"rows": 0, "passed": 0, "failed": 0, "errors": 0})
    for r in runs:
        c = r.get("condition", "unknown")
        agg[c]["rows"] += 1
        st = r.get("pytest_status", "")
        if st == "passed":
            agg[c]["passed"] += 1
        elif st == "failed":
            agg[c]["failed"] += 1
        else:
            agg[c]["errors"] += 1
    lines = ["| condition | rows | pytest passed | failed | other |", "|---|---|---|---|---|"]
    for c, v in sorted(agg.items()):
        lines.append(f"| {c} | {v['rows']} | {v['passed']} | {v['failed']} | {v['errors']} |")
    return "\n".join(lines) + "\n"


def _comparison_table(runs: list[dict[str, str]]) -> str:
    lines = [
        "| function | condition | stage | AR flagged | unlabeled | total asserts | pytest | killed | survived | score | mutation status |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in runs:
        lines.append(
            f"| {r.get('function_id','')} | {r.get('condition','')} | {r.get('stage','')} | "
            f"{r.get('ar_flagged_tests','')} | {r.get('ar_unlabeled_asserts','')} | {r.get('ar_total_asserts','')} | "
            f"{r.get('pytest_status','')} | {r.get('mutants_killed','')} | {r.get('mutants_survived','')} | "
            f"{r.get('mutation_score','')} | {r.get('mutation_status','')} |"
        )
    return "\n".join(lines) + "\n"


def _notes(runs: list[dict[str, str]], manifest: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append(f"- Mode: {manifest.get('mode', 'unknown')}; real_or_synthetic: {manifest.get('real_or_synthetic', 'unknown')}.")
    # mutation non-ok
    nonok = [r for r in runs if r.get("mutation_status") not in ("ok", "", None)]
    if nonok:
        lines.append("- Mutations not scored (status != ok):")
        for r in nonok:
            lines.append(f"  - {r.get('run_id')}: {r.get('mutation_status')}")
    else:
        lines.append("- All evaluated versions with passing baseline have mutation scores.")
    # baseline failures
    bf = [r for r in runs if r.get("pytest_status") != "passed"]
    if bf:
        lines.append("- Versions not passing pytest (no mutation run):")
        for r in bf:
            lines.append(f"  - {r.get('run_id')}: {r.get('pytest_status')}")
    # parse/collection hints
    lines.append("- Detector is a static heuristic; see criterios_detector.md for limitations.")
    lines.append("- No causal/statistical inference should be drawn from this pilot.")
    return "\n".join(lines) + "\n"
