"""Run a small demo using replay/synthetic data or real LLM if configured."""
import subprocess, sys, os
from pathlib import Path

root = Path(__file__).resolve().parents[1]
os.chdir(root)
if os.getenv("LLM_API_KEY"):
    subprocess.run([sys.executable, "-m", "ar_pilot.cli", "run", "--config", "configs/pilot.json", "--output", "artifacts/local_run", "--limit", "1"], check=True)
else:
    subprocess.run([sys.executable, "-m", "ar_pilot.cli", "replay", "--fixture", "artifacts/demo/generations.jsonl", "--output", "artifacts/replay_run"], check=True)
PY