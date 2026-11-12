"""Cut 0.5.1: the tag that actually contains what the README documents."""

import json
import pathlib
import re

ROOT = pathlib.Path(r"D:\Desktop\busted")
OLD, NEW = "0.5.0", "0.5.1"

for rel in ("pyproject.toml", "greenwash/__init__.py"):
    path = ROOT / rel
    text = path.read_text(encoding="utf-8")
    text = text.replace(f'version = "{OLD}"', f'version = "{NEW}"')
    text = text.replace(f'__version__ = "{OLD}"', f'__version__ = "{NEW}"')
    path.write_text(text, encoding="utf-8", newline="\n")
    print(rel, "->", NEW)

for rel in (".claude-plugin/plugin.json",
            "benchmark/plugins/greenwash-skill-only/.claude-plugin/plugin.json",
            "codex/plugin.json", "codex/.codex-plugin/plugin.json"):
    path = ROOT / rel
    data = json.loads(path.read_text(encoding="utf-8"))
    data["version"] = NEW
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(rel, "->", NEW)

readme = ROOT / "README.md"
text = readme.read_text(encoding="utf-8")
text = text.replace(f"@v{OLD}", f"@v{NEW}")
text = text.replace("version-0.4.2-orange.svg", f"version-{NEW}-orange.svg")
text = text.replace(">0.4.2</a>", f">{NEW}</a>")
text = text.replace("greenwash-0.4.2.tgz", f"greenwash-{NEW}.tgz")
readme.write_text(text, encoding="utf-8", newline="\n")
print("README.md references ->", NEW)

guide = ROOT / "docs/ADOPTION_GUIDE.md"
if guide.is_file():
    g = guide.read_text(encoding="utf-8").replace("@v0.4.2", f"@v{NEW}")
    guide.write_text(g, encoding="utf-8", newline="\n")
    print("ADOPTION_GUIDE.md ->", NEW)

# The changelog: add a 0.5.1 section above 0.5.0.
changelog = ROOT / "CHANGELOG.md"
text = changelog.read_text(encoding="utf-8")
section = """## 0.5.1 -- 2026-11-12

### Fixed

- **The release tag now contains what the README documents.** `v0.5.0` was cut
  before the Requirement Coverage Engine landed, so the documented install
  produced a CLI without `greenwash coverage`. This tag is the first one whose
  Contents match the documentation; the release workflow fails the build when
  the tag and `greenwash.__version__` disagree, which is what would have caught
  it.
- **The README's version badge and install lines** pointed at 0.4.2 and 0.5.0.

"""
text = text.replace("## 0.5.0 -- 2026-11-12", section + "## 0.5.0 -- 2026-11-12", 1)
changelog.write_text(text, encoding="utf-8", newline="\n")
print("CHANGELOG.md -> 0.5.1 section added")
