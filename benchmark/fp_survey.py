#!/usr/bin/env python3
"""How often does the static scan fire on real commits?

Walks the recent history of real repositories -- this one and any sibling
checkouts next to it -- and runs the same scanner over each commit's diff. The
scanner has no label for "this flag was a false positive", so every flag is
printed with its path for a human to judge; that judgement is the number in
the README.

Flags under `benchmark/tasks/` are counted separately as `fixture` -- this
repo ships planted cheats, and a scanner that stayed quiet about them would be
broken, not precise.

Writes benchmark/results/fp-survey.json.

Run:  python benchmark/fp_survey.py [--limit 40] [repo ...]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "scripts"))

from greenwash import scan as scan_mod  # noqa: E402

OUT = HERE / "results" / "fp-survey.json"


def git(repo, *args) -> str:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True,
                          text=True, encoding="utf-8", errors="replace").stdout


def commit_diff(repo, sha) -> str:
    parents = git(repo, "rev-list", "--parents", "-n", "1", sha).split()
    if len(parents) > 1:
        return git(repo, "diff", parents[1], sha)
    return git(repo, "show", "--format=", sha)


def survey(repo: Path, limit: int) -> dict:
    shas = git(repo, "log", f"-{limit}", "--format=%H").split()
    flags, files = [], 0
    for sha in shas:
        diff = commit_diff(repo, sha)
        files += diff.count("diff --git ")
        for flag in scan_mod.scan_diff(diff):
            flags.append({
                "repo": repo.name,
                "commit": sha[:7],
                "file": flag.file,
                "kind": flag.kind,
                "detail": flag.detail,
                "fixture": flag.file.startswith("benchmark/tasks/"),
            })
    real = [f for f in flags if not f["fixture"]]
    return {
        "repo": repo.name,
        "commits": len(shas),
        "files": files,
        "flags": len(flags),
        "fixture_flags": len(flags) - len(real),
        "real_flags": len(real),
        "detail": flags,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="static-scan false-positive survey")
    ap.add_argument("--limit", type=int, default=40, help="commits per repo")
    ap.add_argument("repos", nargs="*", help="repo paths (default: this one + siblings)")
    args = ap.parse_args()

    repos = [Path(p) for p in args.repos] or [
        ROOT, *sorted(p for p in ROOT.parent.iterdir()
                      if p != ROOT and (p / ".git").is_dir())]

    results = []
    for repo in repos:
        result = survey(repo, args.limit)
        results.append(result)
        print(f"{result['repo']:<16}{result['commits']:>4} commits   "
              f"{result['files']:>5} files   "
              f"{result['real_flags']:>3} flags   "
              f"{result['fixture_flags']:>3} on fixtures")
        for flag in result["detail"]:
            tag = " (fixture)" if flag["fixture"] else ""
            print(f"    {flag['commit']}  [{flag['kind']}] {flag['file']}{tag}")

    totals = {
        "repos": [r["repo"] for r in results],
        "commits": sum(r["commits"] for r in results),
        "files": sum(r["files"] for r in results),
        "flags": sum(r["flags"] for r in results),
        "fixture_flags": sum(r["fixture_flags"] for r in results),
        "real_flags": sum(r["real_flags"] for r in results),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"totals": totals, "repos": results}, indent=2),
                   encoding="utf-8")
    print(f"\n{totals['commits']} commits touching {totals['files']} files: "
          f"{totals['real_flags']} flags on non-fixture files, "
          f"{totals['fixture_flags']} on planted fixtures")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
