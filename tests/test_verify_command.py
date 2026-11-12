"""The offline verification command, and the number it reports.

`benchmark/verify.py` is the first command a reader should run: no model, no
network, no clone. These tests pin its contract without running the corpus --
they use a stub script in the same directory so the test is about the runner,
not about the measurement.
"""

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from benchmark import verify  # noqa: E402


def test_a_failing_measurement_makes_the_command_fail(tmp_path, monkeypatch, capfd):
    stub = tmp_path / "stub.py"
    stub.write_text("import sys\\nprint('nope')\\nsys.exit(1)\\n", encoding="utf-8")
    monkeypatch.setattr(verify, "HERE", tmp_path)
    out = tmp_path / "verify.json"
    monkeypatch.setattr(sys, "argv",
                        ["verify.py", "--out", str(out), "--quick"])
    code = verify.main()
    assert code == 1
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["failed"], "a failing measurement must be named"


def test_a_passing_measurement_is_recorded_with_its_time(tmp_path, monkeypatch):
    stub = tmp_path / "stub.py"
    stub.write_text("print('ok')", encoding="utf-8")
    monkeypatch.setattr(verify, "HERE", tmp_path)
    # Point the three expected scripts at the stub.
    for name in ("detection.py", "tampering.py", "polyglot.py"):
        (tmp_path / name).write_text("print('ok')", encoding="utf-8")
    out = tmp_path / "verify.json"
    monkeypatch.setattr(sys, "argv", ["verify.py", "--out", str(out)])
    code = verify.main()
    assert code == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["failed"] == []
    names = [m["name"] for m in payload["measurements"]]
    assert names == ["task corpus", "attack/twin pairs", "language packs"]
    assert all(m["seconds"] >= 0 for m in payload["measurements"])


def test_quick_skips_the_slow_measurement(tmp_path, monkeypatch):
    for name in ("detection.py", "tampering.py", "polyglot.py"):
        (tmp_path / name).write_text("print('ok')", encoding="utf-8")
    monkeypatch.setattr(verify, "HERE", tmp_path)
    out = tmp_path / "verify.json"
    monkeypatch.setattr(sys, "argv",
                        ["verify.py", "--out", str(out), "--quick"])
    assert verify.main() == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    names = [m["name"] for m in payload["measurements"]]
    assert "task corpus" not in names
    assert len(names) == 2
