#!/usr/bin/env python3
"""Sync the checker and skill into the benchmark's skill-only control plugin.

The `skill-only` state must run the same detector as the full plugin -- the
Stop hook is the only intended difference -- or the benchmark ends up
comparing two different checkers instead of one checker with and without a
hook. Run this after changing anything under greenwash/ or skills/;
tests/test_manifests.py fails if the copies drift.

Run:  python benchmark/tools/sync_skill_only.py
"""

from __future__ import annotations

import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
PLUGIN = HERE.parent / "plugins" / "greenwash-skill-only"

PACKAGE = [path.relative_to(ROOT).as_posix()
           for path in sorted((ROOT / "greenwash").rglob("*.py")) if "__pycache__" not in path.parts]

FILES = [
    "scripts/greenwash_check.py",
    "skills/greenwash/SKILL.md",
    *PACKAGE,
]

SYNCED_DIRS = [PLUGIN / "scripts", PLUGIN / "greenwash"]


def main() -> None:
    for rel in FILES:
        src, dst = ROOT / rel, PLUGIN / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    expected = {PLUGIN / rel for rel in FILES}
    for directory in SYNCED_DIRS:
        if not directory.is_dir():
            continue
        for stale in directory.rglob("*"):
            if stale.is_file() and stale not in expected:
                stale.unlink()
                print(f"removed stale {stale.relative_to(PLUGIN)}")
        for stale_dir in sorted((d for d in directory.rglob("*") if d.is_dir()),
                                reverse=True):
            if stale_dir not in {p.parent for p in expected} and not any(stale_dir.iterdir()):
                stale_dir.rmdir()
                print(f"removed empty {stale_dir.relative_to(PLUGIN)}")

    print(f"synced {len(FILES)} files -> {PLUGIN}")


if __name__ == "__main__":
    main()
