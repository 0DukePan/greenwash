#!/usr/bin/env python3
"""Generate the host instruction files from `skills/greenwash/SKILL.md`.

Every agent host that reads an instruction file gets the same rules -- only the
location and the frontmatter differ -- so they cannot drift. The Claude Code
plugin additionally ships the Stop hook (`hooks/hooks.json`); everywhere else
this ruleset is a check the agent is asked to run, not one it cannot skip.

Run:  python adapters/sync_instructions.py [--check]
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SOURCE = ROOT / "skills" / "greenwash" / "SKILL.md"

HEADER = ("<!-- generated from skills/greenwash/SKILL.md by "
          "adapters/sync_instructions.py -- edit the skill, then rerun -->\n")

PREAMBLE = ("Point `GREENWASH` at your greenwash checkout before running these\n"
            "commands (or replace it with the absolute path).\n")

CURSOR_FRONTMATTER = (
    "---\n"
    "description: greenwash -- prove \"tests pass\" with the literal command and\n"
    "  output, and run the held-out suite when one exists\n"
    "globs:\n"
    "alwaysApply: true\n"
    "---\n\n"
)

# host -> (relative file, frontmatter)
TARGETS = {
    "AGENTS.md": None,
    "GEMINI.md": None,
    ".github/copilot-instructions.md": None,
    ".cursor/rules/greenwash.mdc": CURSOR_FRONTMATTER,
    ".clinerules/greenwash.md": None,
    ".windsurf/rules/greenwash.md": None,
}


def rendered() -> dict[str, str]:
    text = SOURCE.read_text(encoding="utf-8")
    body = text.split("---", 2)[2].lstrip("\n")
    body = body.replace("# greenwash\n", f"# greenwash\n\n{PREAMBLE}\n", 1)
    body = body.replace("${CLAUDE_PLUGIN_ROOT}/scripts/greenwash_check.py",
                        "$GREENWASH/scripts/greenwash_check.py")
    return {rel: HEADER + (front or "") + body
            for rel, front in TARGETS.items()}


def main() -> None:
    stale = []
    for rel, content in rendered().items():
        path = ROOT / rel
        if "--check" in sys.argv:
            current = path.read_text(encoding="utf-8") if path.is_file() else ""
            if current != content:
                stale.append(rel)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"wrote {rel}")

    if "--check" in sys.argv:
        if stale:
            sys.exit(f"out of sync with skills/greenwash/SKILL.md: {stale}\n"
                     "run python adapters/sync_instructions.py")
        print("host instruction files are in sync")


if __name__ == "__main__":
    main()
