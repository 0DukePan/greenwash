"""Manifest checks that run without the Claude Code CLI (so CI can enforce them).

These catch the class of bug we already hit once: a plugin manifest or hook
that points at a file that no longer exists.
"""

import configparser
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def test_workflow_and_action_are_valid_yaml():
    """A YAML error here is not a red CI job, it is no CI job at all.

    GitHub skips a workflow it cannot parse, and it skipped this repository's
    Action once already. The check is cheap and the failure mode is silent,
    which is the worst combination.
    """
    yaml = pytest.importorskip("yaml", reason="PyYAML is not installed")

    workflow = yaml.safe_load((ROOT / ".github" / "workflows" / "ci.yml")
                              .read_text(encoding="utf-8"))
    assert workflow["jobs"], "the workflow has no jobs"
    for name, job in workflow["jobs"].items():
        assert job.get("runs-on"), f"{name} has no runner"
        assert job.get("steps"), f"{name} has no steps"
        for step in job["steps"]:
            assert step.get("uses") or step.get("run"), f"{name}: empty step {step}"

    action = yaml.safe_load((ROOT / "action.yml").read_text(encoding="utf-8"))
    assert action["runs"]["using"] == "composite"
    assert action["runs"]["steps"], "the Action does nothing"


def test_plugin_manifest():
    manifest = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert manifest["name"] == "greenwash"
    assert manifest["version"]
    assert manifest.get("author"), "plugin.json should credit an author"


def test_marketplace_manifest():
    manifest = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    assert manifest["name"]
    assert manifest["owner"]["name"]
    assert any(p["name"] == "greenwash" for p in manifest["plugins"])


def test_stop_hook_points_at_an_existing_script():
    hooks = json.loads((ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    handler = hooks["hooks"]["Stop"][0]["hooks"][0]
    assert handler["type"] == "command"
    referenced = " ".join([handler.get("command", ""), *handler.get("args", [])])
    assert "greenwash_hook.py" in referenced
    assert (ROOT / "scripts" / "greenwash_hook.py").is_file()


def test_skill_frontmatter_names_the_skill():
    text = (ROOT / "skills" / "greenwash" / "SKILL.md").read_text(encoding="utf-8")
    assert text.startswith("---")
    assert "name: greenwash" in text.split("---")[1]


def test_host_instruction_files_are_in_sync():
    # AGENTS.md, Cursor, Copilot, Cline, Windsurf and Gemini copies are
    # generated from the skill, so the rules cannot drift between hosts.
    result = subprocess.run(
        [sys.executable, str(ROOT / "adapters" / "sync_instructions.py"), "--check"],
        capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_pytest_config_restricts_collection_to_the_unit_tests():
    # Without testpaths, `python -m pytest -q` also collects the benchmark
    # task fixtures, which fails on import and pollutes the workspaces.
    config = configparser.ConfigParser()
    config.read(ROOT / "pytest.ini")
    assert config["pytest"]["testpaths"].split() == ["tests"]


PLUGIN = ROOT / "benchmark" / "plugins" / "greenwash-skill-only"
SYNCED = [
    "scripts/greenwash_check.py",
    "skills/greenwash/SKILL.md",
    *[path.relative_to(ROOT).as_posix()
      for path in sorted((ROOT / "greenwash").rglob("*.py"))
      if "__pycache__" not in path.parts],
]


def test_skill_only_plugin_matches_the_main_checker():
    drifted = [rel for rel in SYNCED
               if not (PLUGIN / rel).is_file()
               or (ROOT / rel).read_bytes() != (PLUGIN / rel).read_bytes()]
    assert drifted == [], (
        f"skill-only plugin out of sync: {drifted}; "
        "run python benchmark/tools/sync_skill_only.py")


def test_skill_only_plugin_has_no_hook():
    # The Stop hook is the one intended difference between the two states.
    assert not (PLUGIN / "scripts" / "greenwash_hook.py").exists()
    assert not (PLUGIN / "hooks").exists()
