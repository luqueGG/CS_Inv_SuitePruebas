"""Isolated execution of pytest and mutmut via subprocess."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class PytestResult:
    status: str  # passed | failed | error | timeout | collection_error
    returncode: int | None
    passed: int
    failed: int
    errors: int
    skipped: int
    log: str
    elapsed: float


@dataclass
class MutationResult:
    status: str  # ok | baseline_failed | no_mutants | error | timeout
    killed: int | None
    survived: int | None
    other: int | None
    score: float | None
    log: str
    raw_stats: dict[str, Any]


def _run(cmd: list[str], cwd: Path, timeout: int, log_path: Path) -> tuple[int | None, str, float]:
    import time
    start = time.time()
    try:
        proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=timeout, shell=False)
        out = (proc.stdout or "") + "\n" + (proc.stderr or "")
        log_path.write_text(out, encoding="utf-8")
        return proc.returncode, out, time.time() - start
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or "") + "\n" + (e.stderr or "") + "\nTIMEOUT"
        log_path.write_text(out, encoding="utf-8")
        return None, out, time.time() - start


def run_pytest(workdir: Path, test_file: str, timeout: int = 120, log_path: Path | None = None) -> PytestResult:
    workdir.mkdir(parents=True, exist_ok=True)
    if log_path is None:
        log_path = workdir / "pytest.log"
    cmd = [sys.executable, "-m", "pytest", "-q", "--no-header", test_file]
    rc, out, elapsed = _run(cmd, workdir, timeout, log_path)
    if rc is None:
        return PytestResult("timeout", None, 0, 0, 0, 0, out, elapsed)
    # parse counts from pytest short summary
    passed = failed = errors = skipped = 0
    for line in out.splitlines():
        low = line.lower()
        # lines like "3 passed, 1 failed in 0.1s"
        if " passed" in low or " failed" in low or " error" in low:
            # attempt parse tokens
            import re
            for m in re.finditer(r"(\d+)\s+(passed|failed|error|errors|skipped)", low):
                n = int(m.group(1)); kind = m.group(2)
                if kind == "passed":
                    passed = n
                elif kind == "failed":
                    failed = n
                elif kind.startswith("error"):
                    errors = n
                elif kind == "skipped":
                    skipped = n
    if rc == 0:
        status = "passed"
    elif rc == 1:
        status = "failed"
    elif rc == 2:
        status = "collection_error" if ("error" in out.lower() or "cannot collect" in out.lower()) else "error"
    elif rc == 5:
        status = "no_tests"
    else:
        status = "error"
    # collection error detection
    if "SyntaxError" in out or "ImportError" in out or "ModuleNotFoundError" in out or "CollectionError" in out:
        if rc not in (0, 1):
            status = "collection_error"
    return PytestResult(status, rc, passed, failed, errors, skipped, out, elapsed)


def prepare_workdir(dest: Path, source_path: Path, test_code: str, test_filename: str = "test_gen.py") -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    # copy full examples module as examples.py
    shutil.copyfile(source_path, dest / "examples.py")
    (dest / test_filename).write_text(test_code, encoding="utf-8")
    # mutmut config
    cfg = """[tool.mutmut]
source_paths = ["examples.py"]
pytest_add_cli_args = ["-q"]
pytest_add_cli_args_test_selection = ["%s"]
""" % test_filename
    (dest / "pyproject.toml").write_text(cfg, encoding="utf-8")
    return dest


def run_mutmut(workdir: Path, timeout: int = 300, log_path: Path | None = None) -> MutationResult:
    workdir.mkdir(parents=True, exist_ok=True)
    if log_path is None:
        log_path = workdir / "mutmut.log"
    # clean mutants dir
    mutants = workdir / "mutants"
    if mutants.exists():
        shutil.rmtree(mutants, ignore_errors=True)
    # remove cache
    for c in workdir.glob(".mutmut-cache*"):
        if c.is_dir():
            shutil.rmtree(c, ignore_errors=True)
        else:
            c.unlink(missing_ok=True)
    cmd = [sys.executable, "-m", "mutmut", "run"]
    rc, out, elapsed = _run(cmd, workdir, timeout, log_path)
    if rc is None:
        return MutationResult("timeout", None, None, None, None, out, {})
    # export cicd stats
    _run([sys.executable, "-m", "mutmut", "export-cicd-stats"], workdir, timeout, log_path)
    stats_path = mutants / "mutmut-cicd-stats.json"
    raw = {}
    if stats_path.exists():
        try:
            raw = json.loads(stats_path.read_text())
        except Exception:
            raw = {}
    if rc != 0 and not raw:
        # maybe baseline failed
        if "failed" in out.lower() or "error" in out.lower():
            return MutationResult("error", None, None, None, None, out, raw)
    killed = raw.get("killed")
    survived = raw.get("survived")
    other = (raw.get("timeout", 0) + raw.get("suspicious", 0) + raw.get("skipped", 0) + raw.get("no_tests", 0) + raw.get("segfault", 0))
    score = None
    if killed is not None and survived is not None and (killed + survived) > 0:
        score = round(killed / (killed + survived) * 100, 2)
    status = "ok"
    if killed is None and survived is None:
        status = "error"
    return MutationResult(status, killed, survived, other, score, out, raw)
