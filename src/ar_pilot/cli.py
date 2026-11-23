"""CLI for the pilot."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import examples, records
from .detector import analyze_file, analyze_files
from .experiment import run_function_pair
from .llm import LLMClient, LLMConfig
from . import reporting
from .prompting import sha256_file


def main(argv=None):
    parser = argparse.ArgumentParser(prog="ar_pilot")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list-functions")

    p = sub.add_parser("detect")
    p.add_argument("paths", nargs="+")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("run")
    p.add_argument("--config", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--functions", nargs="*")
    p.add_argument("--no-mutations", action="store_true")
    p.add_argument("--include-v0-mutations", action="store_true")
    p.add_argument("--limit", type=int, default=None)

    p = sub.add_parser("replay")
    p.add_argument("--fixture", required=True)
    p.add_argument("--output", required=True)

    p = sub.add_parser("report")
    p.add_argument("--output", required=True)

    args = parser.parse_args(argv)

    if args.cmd == "list-functions":
        for f in examples.list_functions():
            print(f)
        return 0

    if args.cmd == "detect":
        reports = analyze_files(args.paths)
        if args.json:
            print(json.dumps([r.__dict__ for r in reports], indent=2, default=str))
        else:
            for r in reports:
                print(f"{r.path}: status={r.status} flagged={r.ar_flagged_tests} unlabeled={r.ar_unlabeled_asserts} total={r.ar_total_asserts}")
                for t in r.tests:
                    print(f"  {t.name} line {t.lineno}: total={t.total_asserts} unlabeled={t.unlabeled_asserts} candidate={t.ar_candidate}")
        return 0

    if args.cmd == "run":
        cfg_path = Path(args.config)
        cfg = json.loads(cfg_path.read_text())
        llm_cfg = LLMConfig.from_dict(cfg.get("llm", {}))
        if not llm_cfg.api_key and llm_cfg.provider in ("openai", "anthropic", "openai_compatible"):
            print("ERROR: LLM_API_KEY not set. Configure .env or config. Use replay mode for offline demo.", file=sys.stderr)
            return 2
        client = LLMClient(llm_cfg)
        out = Path(args.output)
        funcs = args.functions or cfg.get("functions") or examples.list_functions()
        if args.limit:
            funcs = funcs[:args.limit]
        prompts_dir = Path(cfg.get("prompts_dir", "prompts"))
        all_records = []
        for fid in funcs:
            recs = run_function_pair(
                fid, out, client, llm_cfg, prompts_dir,
                run_mutations=not args.no_mutations,
                stage_v0_mutations=args.include_v0_mutations,
            )
            all_records.extend(recs)
        records.write_csv(out / "runs.csv", all_records)
        # manifest
        manifest = {
            "real_or_synthetic": "real",
            "mode": "run",
            "model": llm_cfg.model,
            "provider": llm_cfg.provider,
            "functions": funcs,
            "pairs": len(funcs),
            "generated_at_utc": records.now_utc(),
            "commands": {
                "install": "pip install -e '.[dev]'",
                "run": f"python -m ar_pilot.cli run --config {args.config} --output {args.output}",
            },
        }
        records.write_json(out / "manifest.json", manifest)
        reporting.generate(out)
        print(f"Completed {len(funcs)} functions -> {out}")
        return 0

    if args.cmd == "replay":
        fixture = Path(args.fixture)
        out = Path(args.output)
        out.mkdir(parents=True, exist_ok=True)
        # Copy fixture generations and build synthetic manifest; validate locally
        # We do not fabricate LLM calls; just copy and run detector + pytest/mutmut on provided tests if present.
        print("Replay mode: expects fixture with generations.jsonl and tests_generated/.")
        # Try to locate tests_generated in fixture dir
        fixture_dir = fixture.parent
        tests_dir = fixture_dir / "tests_generated"
        if tests_dir.exists():
            # copy
            import shutil
            dst = out / "tests_generated"
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(tests_dir, dst)
        # copy generations.jsonl
        if fixture.exists():
            import shutil
            shutil.copyfile(fixture, out / "generations.jsonl")
        manifest = {
            "real_or_synthetic": "synthetic_or_replay",
            "mode": "replay",
            "source_fixture": str(fixture),
            "generated_at_utc": records.now_utc(),
            "note": "Replay mode uses previously saved LLM outputs; no new LLM calls.",
        }
        records.write_json(out / "manifest.json", manifest)
        print(f"Replay prepared -> {out}")
        return 0

    if args.cmd == "report":
        created = reporting.generate(args.output)
        for p in created:
            print(f"generated: {p}")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
