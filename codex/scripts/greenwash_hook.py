#!/usr/bin/env python3
"""greenwash's Codex Stop hook: the strict profile, on by default.

Codex calls this when the agent tries to end its turn. It runs the same
checker the Claude hook runs, with `--strict`, and decides:

  exit 0   allow the stop. The report is printed either way.
  exit 2   block the stop and hand the findings back, on stderr.

Three things are deliberate.

**Strict is the default here, and it is not the CLI default.** A plugin is
opted into once, by someone who wants a gate; a CLI invocation is not. The
plugin profile therefore runs the longer decision table -- a review-only
finding blocks until it is waived -- while `greenwash` on the command line
still reports and exits 0.

**The plugin root is resolved defensively.** Codex exposes `PLUGIN_ROOT`;
`CODEX_PLUGIN_ROOT` is accepted as a compatibility spelling, and when neither
is set the hook uses its own location. A host that substitutes a token this
file does not know about still starts the hook -- which matters, because a
hook that cannot start is a hook that does not exist.

**A broken checker blocks at most the budget, and never claims a pass.** If the
CLI cannot run, the hook prints "could not verify" and, because the Codex
profile is strict, blocks at most three times before ending in UNRESOLVED AT
STOP. A crash must never read as a pass, and a repository the verifier can
never satisfy must never lock a developer out for good. This hook always runs
the strict profile; the CLI's own report mode, where a broken checker is
printed and not blocked, is a different surface.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))

from greenwash import hooking  # noqa: E402


def plugin_root() -> str:
    for name in ("PLUGIN_ROOT", "CODEX_PLUGIN_ROOT", "CLAUDE_PLUGIN_ROOT"):
        value = os.environ.get(name)
        if value and os.path.isdir(value):
            return value
    return os.path.dirname(HERE)


def interpreter_candidates() -> list:
    """Whichever Python the host has. `py -3` first on Windows, like the shim."""
    if os.name == "nt":
        return [(sys.executable, []), ("py", ["-3"]), ("python", [])]
    return [(sys.executable, []), ("python3", []), ("python", [])]


def report_command(root: str, claim: str) -> list:
    command = ["-m", "greenwash", "--strict", "--json", "--no-color"]
    if claim:
        command += ["--claim", claim]
    return command


def python_path(root: str) -> str:
    """Where the checker may be importable from.

    `pipx install greenwash-cli` is the supported install and needs none of
    this. The parent directory is here for the other case: a checkout of this
    repository keeps the plugin in `codex/` and the package one level up, and
    a hook that only works after an install is a hook nobody can try first.
    """
    parts = [root, os.path.dirname(root)]
    existing = os.environ.get("PYTHONPATH")
    if existing:
        parts.append(existing)
    return os.pathsep.join(parts)


def run_report(root: str, payload: dict):
    """(report, exit_code, error). A report or an error, never both.

    A timeout is not retried on the next interpreter candidate: the command
    hung, and a second run of a hung command only hangs again.
    """
    claim = ""
    for key in ("claim", "summary", "task"):
        if isinstance(payload.get(key), str):
            claim = payload[key][:400]
            break

    env = dict(os.environ)
    env["PYTHONPATH"] = python_path(root)
    command = report_command(root, claim)
    error = ""
    for executable, prefix in interpreter_candidates():
        try:
            stdout, stderr, returncode = hooking.run_with_deadline(
                [executable, *prefix, *command], env=env,
                timeout=hooking.hook_timeout(default=270))
        except subprocess.TimeoutExpired as exc:
            raise exc
        except (OSError, subprocess.SubprocessError) as exc:
            error = str(exc)
            continue
        try:
            return json.loads(stdout), returncode, None
        except (json.JSONDecodeError, ValueError):
            error = (f"{executable} exited {returncode} without a report: "
                     f"{(stderr or '').strip()[:200]}")
    return None, 0, error


def _checks(verification: dict) -> list:
    lines = []
    outcome = verification.get("outcome")
    if outcome and outcome != "not_requested":
        passed, total = verification.get("tests_passed"), verification.get("tests_run")
        lines.append(f"visible tests: {passed}/{total}" if total else f"visible tests: {outcome}")
    else:
        lines.append("visible tests: not run")
    for label, key in (("held-out", "heldout"), ("integrity", "integrity"),
                       ("baseline", "baseline")):
        value = verification.get(key)
        if value and value != "not_requested":
            lines.append(f"{label}: {value}")
    return lines


def describe(report: dict) -> str:
    """Verdict, checks run, blocked reasons, waiver status, next step."""
    gate = report.get("gate") or {}
    verification = report.get("verification") or {}
    confidence = report.get("confidence") or {}
    signals = report.get("signals") or []
    blocked = gate.get("state") == "blocked"

    head = "BLOCKED" if blocked else "allowed"
    lines = [f"greenwash (strict): {head} -- {report.get('verdict', 'INCONCLUSIVE')} "
             f"({str(confidence.get('level', '')).lower()} confidence)"]

    lines.append("checks: " + "; ".join(_checks(verification)))

    if blocked:
        for reason in (gate.get("reasons") or [])[:4]:
            lines.append(f"blocked: {reason}")
    for notice in (gate.get("notices") or [])[:2]:
        lines.append(f"note: {notice}")

    waived = [s for s in signals if (s.get("waiver") or {}).get("status") == "active"]
    lapsed = [s for s in signals if s.get("waiver")
              and (s.get("waiver") or {}).get("status") != "active"]
    lines.append(f"waivers: {len(waived)} active, {len(lapsed)} lapsed")

    for signal in signals[:6]:
        where = f" {signal.get('files', [''])[0]}" if signal.get("files") else ""
        waived = signal.get("waiver") or {}
        if waived.get("status") == "active":
            mark = " (waived, self-issued)" if waived.get("self_issued") else " (waived)"
        else:
            mark = ""
        lines.append(f"  [{signal.get('rule_id', '?')}]{where} "
                     f"{signal.get('explanation', '')}{mark}")

    if blocked:
        lines.append("next: fix the finding, or record a decision with "
                     "`greenwash waive --rule <rule> --path <file> --reason <why> "
                     "--reviewer @you --expires <date>` and stop again.")
    else:
        lines.append("next: nothing to explain. Safe to finish.")
    return "\n".join(lines)


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        payload = {}

    # stop_hook_active announces a retry after an earlier block. It no longer
    # bypasses the gate: the block budget bounds every retry. A payload without
    # a session id is almost always the interpreter-fallback re-run of a chain
    # (`python3 hook || python hook`) on consumed stdin; give it its own budget
    # so the fallback blocks the same way instead of laundering the first run's
    # exit.
    session = str(payload.get("session_id") or "") or f"anonymous-{os.getpid()}"
    root = plugin_root()
    try:
        report, exit_code, error = run_report(root, payload)
    except subprocess.TimeoutExpired as exc:
        report, exit_code, error = None, 0, f"the checker exceeded its deadline ({exc})"
    if report is None:
        # not a pass: strict blocks on the unknown, at most the budget
        text = (f"greenwash: could not verify this turn ({error}); "
                "the diff has NOT been checked. Run `greenwash doctor` to see "
                "what is missing.")
        if hooking.take_block(session_id=session):
            print(text, file=sys.stderr)
            sys.exit(2)
        print(text)
        print(hooking.unresolved_banner())
        sys.exit(0)

    message = describe(report)
    # The CLI owns the policy and its exit code carries it; the wording above is
    # this hook's own. Re-deriving "should this block?" from the verdict here is
    # how the two surfaces would drift apart, so the code is the whole contract.
    if exit_code != 0:
        if hooking.take_block(session_id=session):
            print(message, file=sys.stderr)
            sys.exit(2)
        print(message)
        print(hooking.unresolved_banner())
        sys.exit(0)
    print(message)
    sys.exit(0)


if __name__ == "__main__":
    main()
