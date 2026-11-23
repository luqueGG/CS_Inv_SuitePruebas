"""Orchestration of the paired pilot experiment."""

from __future__ import annotations

import hashlib
import re
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import examples, prompting, records
from .detector import analyze_source
from .llm import LLMClient, LLMConfig
from .runner import prepare_workdir, run_pytest, run_mutmut

CODE_BLOCK_RE = re.compile(r"```(?:python)?\s*\n(.*?)```", re.DOTALL)


def extract_code(text: str) -> str:
    m = CODE_BLOCK_RE.search(text)
    if m:
        return m.group(1).strip() + "\n"
    # fallback: whole text
    return text.strip() + "\n"


def source_of_function(name: str) -> str:
    import inspect
    return inspect.getsource(getattr(examples, name))


def run_function_pair(
    function_id: str,
    output_dir: Path,
    llm: LLMClient,
    config: LLMConfig,
    prompts_dir: Path,
    run_mutations: bool = True,
    stage_v0_mutations: bool = False,
) -> list[records.RunRecord]:
    """Run v0 + generic + ar_specific for one function. Returns list of RunRecords."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    pair_id = f"pair_{function_id}_{uuid.uuid4().hex[:8]}"
    source = source_of_function(function_id)
    source_sha = hashlib.sha256(source.encode()).hexdigest()
    examples_path = Path(examples.__file__)

    records_list: list[records.RunRecord] = []

    # v0 generation
    initial_template = prompting.load_prompt(prompts_dir / "initial.txt")
    initial_prompt = prompting.render(initial_template, function_name=function_id, source=source)
    t0 = time.time()
    resp0 = llm.complete(initial_prompt)
    elapsed0 = time.time() - t0 if resp0.elapsed_seconds else (time.time() - t0)
    v0_code = extract_code(resp0.text) if resp0.text else ""
    v0_sha = hashlib.sha256(v0_code.encode()).hexdigest()

    # save v0 artifacts
    gen_dir = out / "generations"
    gen_dir.mkdir(parents=True, exist_ok=True)
    (out / "tests_generated" / pair_id / "v0").mkdir(parents=True, exist_ok=True)
    v0_dir = out / "tests_generated" / pair_id / "v0"
    v0_dir.mkdir(parents=True, exist_ok=True)
    (v0_dir / "test_v0.py").write_text(v0_code, encoding="utf-8")
    (v0_dir / "raw_response.txt").write_text(resp0.text or "", encoding="utf-8")

    # generations.jsonl entry
    records.append_jsonl(out / "generations.jsonl", {
        "id": f"{pair_id}_v0",
        "parent_id": None,
        "function_id": function_id,
        "stage": "v0",
        "model": config.model,
        "provider": config.provider,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
        "prompt_sha256": prompting.sha256_text(initial_prompt),
        "prompt": initial_prompt,
        "raw_response": resp0.text,
        "extracted_code": v0_code,
        "test_sha256": v0_sha,
        "prompt_tokens": resp0.prompt_tokens,
        "completion_tokens": resp0.completion_tokens,
        "elapsed_seconds": resp0.elapsed_seconds,
        "error": resp0.error,
        "timestamp_utc": records.now_utc(),
    })

    # detector on v0
    det0 = analyze_source(v0_code, f"v0/{function_id}.py")

    # helper to evaluate a version
    def evaluate(version_label: str, condition: str, code: str, prompt_text: str, parent: str, prompt_tokens, completion_tokens, elapsed, raw_text, err):
        nonlocal records_list
        v_dir = out / "tests_generated" / pair_id / version_label
        v_dir.mkdir(parents=True, exist_ok=True)
        (v_dir / f"test_{version_label}.py").write_text(code, encoding="utf-8")
        (v_dir / "raw_response.txt").write_text(raw_text or "", encoding="utf-8")
        code_sha = hashlib.sha256(code.encode()).hexdigest()
        det = analyze_source(code, f"{version_label}/{function_id}.py")
        # generations entry
        records.append_jsonl(out / "generations.jsonl", {
            "id": f"{pair_id}_{version_label}",
            "parent_id": parent,
            "function_id": function_id,
            "stage": version_label,
            "condition": condition,
            "model": config.model,
            "provider": config.provider,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "prompt_sha256": prompting.sha256_text(prompt_text),
            "prompt": prompt_text,
            "raw_response": raw_text,
            "extracted_code": code,
            "test_sha256": code_sha,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "elapsed_seconds": elapsed,
            "error": err,
            "timestamp_utc": records.now_utc(),
        })
        # pytest + mutmut
        run_id = f"{pair_id}_{version_label}"
        exec_dir = out / "exec" / run_id
        exec_dir.mkdir(parents=True, exist_ok=True)
        wd = prepare_workdir(exec_dir, examples_path, code)
        pytest_res = run_pytest(wd, "test_gen.py", timeout=120, log_path=wd / "pytest.log")

        mut_status = None
        mut_killed = mut_survived = mut_other = None
        mut_score = None
        mut_log = ""
        if run_mutations and pytest_res.status == "passed":
            mr = run_mutmut(wd, timeout=300, log_path=wd / "mutmut.log")
            mut_status = mr.status
            mut_killed = mr.killed
            mut_survived = mr.survived
            mut_other = mr.other
            mut_score = mr.score
            mut_log = mr.log
        elif run_mutations:
            mut_status = "baseline_failed"
        else:
            mut_status = "skipped"

        # save logs paths
        (out / "pytest_logs").mkdir(parents=True, exist_ok=True)
        (out / "mutation_logs").mkdir(parents=True, exist_ok=True)
        if (wd / "pytest.log").exists():
            shutil_copy(wd / "pytest.log", out / "pytest_logs" / f"{run_id}.log")
        if (wd / "mutmut.log").exists():
            shutil_copy(wd / "mutmut.log", out / "mutation_logs" / f"{run_id}.log")

        rec = records.RunRecord(
            run_id=run_id,
            pair_id=pair_id,
            function_id=function_id,
            condition=condition,
            stage=version_label,
            model=config.model,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            prompt_sha256=prompting.sha256_text(prompt_text),
            source_sha256=source_sha,
            test_sha256=code_sha,
            pytest_status=pytest_res.status,
            pytest_passed=pytest_res.passed,
            pytest_failed=pytest_res.failed,
            pytest_errors=pytest_res.errors,
            ar_flagged_tests=det.ar_flagged_tests,
            ar_unlabeled_asserts=det.ar_unlabeled_asserts,
            ar_total_asserts=det.ar_total_asserts,
            mutants_killed=mut_killed,
            mutants_survived=mut_survived,
            mutants_other=mut_other,
            mutation_score=mut_score,
            mutation_status=mut_status,
            elapsed_seconds=pytest_res.elapsed + (resp0.elapsed_seconds or 0),
            artifact_dir=str(wd),
        )
        records_list.append(rec)
        return rec

    import shutil as _shutil
    def shutil_copy(a, b):
        _shutil.copyfile(a, b)

    # v0 evaluation (optional mutations)
    if stage_v0_mutations:
        evaluate("v0", "v0", v0_code, initial_prompt, None, resp0.prompt_tokens, resp0.completion_tokens, resp0.elapsed_seconds, resp0.text, resp0.error)

    # detector findings text for AR feedback
    findings_lines = []
    for t in det0.tests:
        if t.ar_candidate:
            lines = ", ".join(str(a["line"]) for a in t.asserts if not a["has_msg"])
            findings_lines.append(f"- {t.name} (line {t.lineno}): {t.unlabeled_asserts} unlabeled asserts out of {t.total_asserts}; unlabeled lines: {lines}")
    if not findings_lines:
        findings_lines.append("- No tests flagged by heuristic (0 unlabeled asserts pairs).")
    findings_text = "\n".join(findings_lines)

    # generic revision
    gen_template = prompting.load_prompt(prompts_dir / "generic_feedback.txt")
    gen_prompt = prompting.render(gen_template, function_name=function_id, v0_code=v0_code)
    t = time.time()
    resp_gen = llm.complete(gen_prompt)
    gen_code = extract_code(resp_gen.text) if resp_gen.text else ""
    evaluate("v1_generic", "generic", gen_code, gen_prompt, f"{pair_id}_v0", resp_gen.prompt_tokens, resp_gen.completion_tokens, resp_gen.elapsed_seconds, resp_gen.text, resp_gen.error)

    # ar-specific revision
    ar_template = prompting.load_prompt(prompts_dir / "ar_feedback.txt")
    ar_prompt = prompting.render(ar_template, function_name=function_id, v0_code=v0_code, findings=findings_text)
    resp_ar = llm.complete(ar_prompt)
    ar_code = extract_code(resp_ar.text) if resp_ar.text else ""
    evaluate("v1_ar_specific", "ar_specific", ar_code, ar_prompt, f"{pair_id}_v0", resp_ar.prompt_tokens, resp_ar.completion_tokens, resp_ar.elapsed_seconds, resp_ar.text, resp_ar.error)

    return records_list
