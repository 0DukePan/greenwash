#!/usr/bin/env python3
"""Exercise the language packs, statically, with no toolchain required.

Python and JavaScript are covered by the 24 tasks, which run real test suites.
Go, Rust, Ruby and Java have no toolchain on the CI runners and no tasks, so
their packs were regex code that nothing exercised -- which is the state this
file exists to end.

Each case is a small tree plus an expectation: which rules must fire, and which
must stay silent. The corpus lives in `benchmark/polyglot/`, and this runner is
what `benchmark/run.py` reports as language coverage.

Run:  python benchmark/polyglot.py [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from greenwash.scan import scan_diff  # noqa: E402

CORPUS = HERE / "polyglot"
TEXT_SUFFIXES = {".go", ".rs", ".rb", ".java", ".js", ".mjs", ".ts", ".py", ".txt", ".md"}


def synth_diff(case_dir: Path) -> str:
    """Every file in a case is new, so every line is an addition."""
    chunks = []
    for path in sorted((case_dir / "files").rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        if path.suffix not in TEXT_SUFFIXES:
            continue
        rel = path.relative_to(case_dir / "files").as_posix()
        lines = path.read_text(encoding="utf-8").splitlines()
        body = "".join(f"+{line}\n" for line in lines)
        chunks.append(f"diff --git a/{rel} b/{rel}\nnew file mode 100644\n--- /dev/null\n"
                      f"+++ b/{rel}\n@@ -0,0 +1,{len(lines)} @@\n{body}")
    return "".join(chunks)


def cases() -> list:
    return sorted(path for path in CORPUS.iterdir() if (path / "case.json").is_file())


def evaluate(case_dir: Path) -> dict:
    case = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
    files = case_dir / "files"
    # explicit root: these paths are relative to the case, not to this checkout
    signals = scan_diff(synth_diff(case_dir), cwd=str(files), root=str(files))
    fired = sorted({signal.rule_id for signal in signals})

    problems = []
    missing = sorted(set(case["must_fire"]) - set(fired))
    if missing:
        problems.append(f"missed {missing}")
    surprise = sorted(set(fired) - set(case["must_fire"]) - set(case["may_fire"]))
    if surprise:
        problems.append(f"unexpected {surprise}")
    false_alarm = sorted(set(fired) & set(case["must_not_fire"]))
    if false_alarm:
        problems.append(f"false alarm {false_alarm}")

    return {"case": case_dir.name, "language": case["language"], "expect": case["expect"],
            "fired": fired, "problems": problems, "ok": not problems,
            "analysis": _analysis_kinds(signals)}


def _analysis_kinds(signals) -> list:
    return sorted({signal.evidence.get("analysis", "regex") for signal in signals})


def run() -> dict:
    results = [evaluate(case) for case in cases()]
    by_language: dict = {}
    for result in results:
        bucket = by_language.setdefault(result["language"], {"cases": 0, "passed": 0})
        bucket["cases"] += 1
        bucket["passed"] += 1 if result["ok"] else 0
    return {"cases": results, "by_language": by_language,
            "passed": sum(1 for r in results if r["ok"]), "total": len(results)}


def main() -> int:
    parser = argparse.ArgumentParser(description="language pack coverage")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    summary = run()
    if args.json:
        print(json.dumps(summary, indent=2))
        return 0 if summary["passed"] == summary["total"] else 1

    print("language pack coverage (static, no toolchain)")
    print()
    print(f"{'case':<20}{'language':<12}{'expected':<10}{'fired':<34}result")
    for result in summary["cases"]:
        fired = ", ".join(result["fired"]) or "-"
        verdict = "ok" if result["ok"] else "FAIL: " + "; ".join(result["problems"])
        print(f"{result['case']:<20}{result['language']:<12}{result['expect']:<10}"
              f"{fired:<34}{verdict}")
    print()
    for language, bucket in sorted(summary["by_language"].items()):
        print(f"  {language:<12}{bucket['passed']}/{bucket['cases']} cases")
    print(f"\n{summary['passed']}/{summary['total']} cases behave as declared")
    return 0 if summary["passed"] == summary["total"] else 1


if __name__ == "__main__":
    sys.exit(main())
