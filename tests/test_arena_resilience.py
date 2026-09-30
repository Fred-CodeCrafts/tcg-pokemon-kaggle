import csv
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def _make_agent(tmp_path, name, source):
    agent_dir = tmp_path / name
    agent_dir.mkdir()
    (agent_dir / "main.py").write_text(source, encoding="utf-8")
    shutil.copyfile(ROOT / "agents" / "random" / "deck.csv", agent_dir / "deck.csv")
    return agent_dir


def _run_arena(tmp_path, agent_a, timeout):
    output = tmp_path / "results.csv"
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "arena.py"),
            "--agent-a",
            str(agent_a),
            "--agent-b",
            str(ROOT / "agents" / "random"),
            "--matches",
            "2",
            "--workers",
            "2",
            "--timeout",
            str(timeout),
            "--seed",
            "20260930",
            "--output",
            str(output),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert completed.returncode == 0, completed.stderr + completed.stdout
    with output.open(newline="", encoding="utf-8") as result_file:
        return list(csv.DictReader(result_file))


def test_agent_exceptions_do_not_stop_batch(tmp_path):
    crash_agent = _make_agent(
        tmp_path,
        "crash_agent",
        "def agent(obs_dict):\n    raise RuntimeError('deliberate crash')\n",
    )
    rows = _run_arena(tmp_path, crash_agent, timeout=15)
    assert len(rows) == 2
    assert all("deliberate crash" in row["errors"] for row in rows)


def test_timed_out_matches_are_killed_and_batch_continues(tmp_path):
    slow_agent = _make_agent(
        tmp_path,
        "slow_agent",
        "import time\n\ndef agent(obs_dict):\n    time.sleep(30)\n    return [0]\n",
    )
    rows = _run_arena(tmp_path, slow_agent, timeout=1.5)
    assert len(rows) == 2
    assert all("timed out" in row["errors"] for row in rows)