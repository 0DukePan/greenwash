"""The Codex plugin: manifests that point at real files, and a gate that starts.

Two classes of bug this catches, both of which have already happened once in
this repository's history: a manifest that names a file which no longer exists,
and a hook command that cannot start on one of the two operating systems the
plugin claims to support. The rest is policy: the Codex gate and the Claude
gate run the same checker, so the same fixture has to reach the same verdict
through both.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CODEX = ROOT / "codex"

BASE = {
    "src/calc.py": "def add(a, b):\n    return a - b\n",
    "tests/test_calc.py": "from src.calc import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n",
    "conftest.py": "",
}


def git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def manifest(path):
    return json.loads(path.read_text(encoding="utf-8"))


def hook_entries():
    return manifest(CODEX / "hooks" / "codex-hooks.json")["hooks"]["Stop"][0]["hooks"]


# ---- the manifests -----------------------------------------------------------

def test_both_manifest_spellings_are_present_and_agree():
    root_manifest = manifest(CODEX / "plugin.json")
    dotted = manifest(CODEX / ".codex-plugin" / "plugin.json")
    assert root_manifest["name"] == dotted["name"] == "greenwash"
    assert root_manifest["version"] == dotted["version"]
    assert root_manifest["hooks"] == dotted["hooks"] == "hooks/codex-hooks.json"


def test_the_version_matches_the_other_two_packages():
    """A version that drifts between four manifests is a release that lies."""
    import re
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    packaged = re.search(r'^version = "([^"]+)"', pyproject, re.M).group(1)
    versions = {
        "pyproject.toml": packaged,
        ".claude-plugin/plugin.json": manifest(ROOT / ".claude-plugin" / "plugin.json")["version"],
        "codex/plugin.json": manifest(CODEX / "plugin.json")["version"],
        "codex/.codex-plugin/plugin.json": manifest(
            CODEX / ".codex-plugin" / "plugin.json")["version"],
    }
    assert len(set(versions.values())) == 1, versions


def test_every_file_the_manifests_name_exists():
    assert (CODEX / "hooks" / "codex-hooks.json").is_file()
    assert (CODEX / "skills" / "greenwash" / "SKILL.md").is_file()
    for entry in hook_entries():
        assert "greenwash_hook.py" in entry["command"]
        assert (CODEX / "scripts" / "greenwash_hook.py").is_file()


def test_the_codex_skill_has_valid_frontmatter():
    text = (CODEX / "skills" / "greenwash" / "SKILL.md").read_text(encoding="utf-8")
    assert text.startswith("---")
    assert "name: greenwash" in text.split("---")[1]


# ---- the hook command, run the way the host runs it --------------------------

def test_the_posix_command_starts_a_hook(tmp_path):
    if os.name == "nt":
        pytest.skip("the POSIX spelling is exercised on the Unix CI runner")
    command = hook_entries()[0]["command"].replace("${PLUGIN_ROOT}", str(CODEX))
    result = subprocess.run(command, shell=True, cwd=tmp_path, capture_output=True,
                            text=True, input=json.dumps({"hook_event_name": "Stop"}),
                            env={**os.environ, "PLUGIN_ROOT": str(CODEX)},
                            encoding="utf-8", errors="replace", timeout=300)
    assert result.returncode == 0, result.stderr
    assert "greenwash" in (result.stdout + result.stderr)


def test_the_windows_command_starts_a_hook(tmp_path):
    if os.name != "nt":
        pytest.skip("the Windows spelling is exercised on the Windows CI runner")
    command = hook_entries()[0]["command_windows"].replace("%PLUGIN_ROOT%", str(CODEX))
    result = subprocess.run(command, shell=True, cwd=tmp_path, capture_output=True,
                            text=True, input=json.dumps({"hook_event_name": "Stop"}),
                            env={**os.environ, "PLUGIN_ROOT": str(CODEX)},
                            encoding="utf-8", errors="replace", timeout=300)
    assert result.returncode == 0, result.stderr


def test_the_windows_command_names_an_interpreter_the_other_one_does_not():
    """python3 on Windows is usually a Microsoft Store stub that fails."""
    entry = hook_entries()[0]
    assert "python3" in entry["command"]
    assert entry["command_windows"].startswith("py -3")
    assert entry["command_windows"] != entry["command"]


# ---- the gate ----------------------------------------------------------------

@pytest.fixture()
def cheat(tmp_path):
    git(tmp_path, "init", "-q")
    for rel, text in BASE.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    git(tmp_path, "add", "-A")
    git(tmp_path, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "base")
    (tmp_path / "src" / "calc.py").write_text("def add(a, b):\n    return 5\n", encoding="utf-8")
    return tmp_path


def codex_hook(cwd, payload=None, env=None):
    return subprocess.run(
        [sys.executable, str(CODEX / "scripts" / "greenwash_hook.py")], cwd=cwd,
        input=json.dumps(payload or {"hook_event_name": "Stop"}),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env={**os.environ, "PYTHONPATH": str(ROOT), "PYTHONIOENCODING": "utf-8",
             **(env or {})}, timeout=300)


def test_strict_is_the_default_profile_here(cheat):
    """No GREENWASH_STRICT, no config file: the plugin is the opt-in."""
    result = codex_hook(cheat)
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert "BLOCKED" in result.stderr
    assert "hardcoded-return" in result.stderr
    assert "next:" in result.stderr


def test_the_message_carries_the_four_things_it_promises(cheat):
    result = codex_hook(cheat)
    message = result.stderr
    assert "greenwash (strict): BLOCKED -- SUSPICIOUS" in message   # verdict
    assert "checks: " in message                                    # checks run
    assert "blocked: " in message                                   # blocked reasons
    assert "waivers: 0 active, 0 lapsed" in message                 # waiver status
    assert "next: " in message                                      # an action


def test_a_clean_tree_is_allowed(cheat):
    (cheat / "src" / "calc.py").write_text("def add(a, b):\n    return a + b\n",
                                           encoding="utf-8")
    result = codex_hook(cheat)
    assert result.returncode == 0, result.stderr
    assert "allowed" in result.stdout


def test_the_hook_resolves_its_own_root_when_no_variable_is_set(cheat):
    """A host that substitutes a token we do not know must still start the hook."""
    env = {key: value for key, value in os.environ.items()
           if key not in ("PLUGIN_ROOT", "CODEX_PLUGIN_ROOT", "CLAUDE_PLUGIN_ROOT")}
    env["PYTHONPATH"] = str(ROOT)
    result = subprocess.run(
        [sys.executable, str(CODEX / "scripts" / "greenwash_hook.py")], cwd=cheat,
        input=json.dumps({"hook_event_name": "Stop"}), capture_output=True, text=True,
        encoding="utf-8", errors="replace", env=env, timeout=300)
    assert result.returncode == 2, (result.stdout, result.stderr)


def test_the_plugin_root_is_resolved_defensively(monkeypatch):
    """PLUGIN_ROOT, then the compatibility spellings, then the hook's own location.

    A wrong-but-set root falls through rather than being honoured: the point of
    the fallback chain is that a host substituting a token this file does not
    know about still starts the hook.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "gw_codex_hook_under_test", CODEX / "scripts" / "greenwash_hook.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    monkeypatch.setenv("PLUGIN_ROOT", str(CODEX))
    assert module.plugin_root() == str(CODEX)

    monkeypatch.setenv("PLUGIN_ROOT", str(CODEX / "does-not-exist"))
    assert module.plugin_root() == str(CODEX), "a path that is not there is not a root"

    monkeypatch.delenv("PLUGIN_ROOT")
    monkeypatch.setenv("CODEX_PLUGIN_ROOT", str(CODEX))
    assert module.plugin_root() == str(CODEX)

    monkeypatch.delenv("CODEX_PLUGIN_ROOT")
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(CODEX))
    assert module.plugin_root() == str(CODEX)

    monkeypatch.delenv("CLAUDE_PLUGIN_ROOT")
    assert module.plugin_root() == str(CODEX), "the hook's own location is the last resort"


def test_the_python_path_covers_a_checkout(tmp_path):
    """The plugin sits in codex/; the package is one level up in a checkout."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "gw_codex_hook_under_test", CODEX / "scripts" / "greenwash_hook.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    parts = module.python_path(str(CODEX)).split(os.pathsep)
    assert parts[0] == str(CODEX)
    assert parts[1] == str(ROOT)


def test_the_two_gates_agree_on_the_same_fixture(cheat):
    """One checker, two host packs: a difference here is a bug in one of them."""
    claude = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "greenwash_hook.py")], cwd=cheat,
        input=json.dumps({"hook_event_name": "Stop"}), capture_output=True, text=True,
        encoding="utf-8", errors="replace",
        env={**os.environ, "PYTHONPATH": str(ROOT), "GREENWASH_STRICT": "1"},
        timeout=300)
    codex = codex_hook(cheat)
    assert claude.returncode == codex.returncode == 2
    assert "hardcoded-return" in claude.stderr and "hardcoded-return" in codex.stderr


def test_invalid_stdin_does_not_crash_the_hook(cheat):
    result = subprocess.run(
        [sys.executable, str(CODEX / "scripts" / "greenwash_hook.py")], cwd=cheat,
        input="not json at all", capture_output=True, text=True, encoding="utf-8",
        errors="replace", env={**os.environ, "PYTHONPATH": str(ROOT)}, timeout=300)
    assert result.returncode in (0, 2)
    assert "Traceback" not in result.stderr
