#!/usr/bin/env python3
"""The offline PR-log collector for the report-only beta trial.

Turns one consented repository's merged pull request export -- the metadata a
hosting API can produce, stored as a JSON file -- plus a local clone into the
friction harness's PR log (benchmark/shadow_friction.py). For each merged
pull request it replays the checker's static scan over the diff from the PR's
merge base to its head, records whether the PR touched tests, whether the scan
flagged, the timestamps the export carries, and any override or opt-out
markers it carries. Every alert is unreviewed: the human judgment file is the
only source of legitimacy, and this tool never writes one.

Consent first. The consent record names the participating repositories, the
contact, the date, and the scope ("history replay, report-only, no comments"),
and a repository absent from it is refused by name before anything is
replayed. A missing commit, a missing field, a malformed timestamp, or a path
leaving the clone is a named refusal -- never a default, never a guess.

This tool is offline and inert: it reads its three inputs, runs git's read-only
plumbing inside the clone with external diff drivers and textconv filters
disabled, scans the diff as text, and writes a local artifact. It makes no
network calls, posts nothing anywhere, and runs no repository code. Time is
bounded per pull request so a pathological diff cannot stall the round.

Export schema (JSON):

  { "repository": "owner/name",
    "pull_requests": [
      { "number": 41,                    -- required
        "merge_base": "<commit id>",     -- required, present in the clone
        "head": "<commit id>",           -- required, present in the clone
        "merged_at": "<ISO 8601>",       -- required
        "flagged_at": "<ISO 8601>",      -- optional, recorded when present
        "resolved_at": "<ISO 8601>",     -- optional, recorded when present
        "override": true,                -- optional marker
        "opt_out": true,                 -- optional marker
        "files": ["path/in/repo"] } ] }  -- optional changed-file paths

Run:  python benchmark/collector.py --export EXPORT.json --clone CLONE \\
        --consent CONSENT.json [--out results/pr-log.json]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from datetime import datetime
from pathlib import Path, PurePosixPath

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from greenwash.scan import scan_diff, summarize  # noqa: E402
from greenwash.scan.languages.packs import is_test_file  # noqa: E402

EXIT_OK = 0
EXIT_REFUSED = 2

DEFAULT_PER_PR_SECONDS = 10.0
SCOPE = "history replay, report-only, no comments"
SHA_RE = re.compile(r"^[0-9a-fA-F]{7,40}$")
WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:")


class Refusal(Exception):
    """The collector refuses to replay: an input is missing or invalid, a
    repository has no recorded consent, or a path leaves the clone. Never a
    default, never a guess."""


def _read_json(path, what: str):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise Refusal(f"{what} at {path} cannot be read: {exc}") from exc


def _load_consent(path) -> set:
    """The consent record: repositories, contact, date and scope, all named.

    Consent is a precondition, not a filter. The record is data, checked into
    the trial directory, and this reads it exactly as written.
    """
    payload = _read_json(path, "the consent record")
    if not isinstance(payload, dict):
        raise Refusal(f"the consent record at {path} is not a JSON object")
    repositories = payload.get("repositories")
    if not isinstance(repositories, list) or not repositories \
            or not all(isinstance(name, str) and name for name in repositories):
        raise Refusal(f'the consent record at {path} does not list repositories '
                      'under "repositories"')
    for field in ("contact", "date", "scope"):
        value = payload.get(field)
        if not isinstance(value, str) or not value:
            raise Refusal(f"the consent record at {path}: field {field!r} is "
                          "missing or not a non-empty string")
    date = payload["date"]
    try:
        datetime.fromisoformat(date.replace("Z", "+00:00"))
    except ValueError as exc:
        raise Refusal(f"the consent record at {path}: field 'date' is not an "
                      f"ISO 8601 timestamp: {date!r}") from exc
    if payload["scope"] != SCOPE:
        raise Refusal(f"the consent record at {path} records scope "
                      f"{payload['scope']!r}, expected {SCOPE!r}")
    return set(repositories)


def _load_export(path):
    payload = _read_json(path, "the PR export")
    if not isinstance(payload, dict):
        raise Refusal(f"the PR export at {path} is not a JSON object")
    repository = payload.get("repository")
    if not isinstance(repository, str) or not repository:
        raise Refusal(f"the PR export at {path}: field 'repository' is missing "
                      "or not a non-empty string")
    entries = payload.get("pull_requests")
    if not isinstance(entries, list):
        raise Refusal(f"the PR export at {path}: field 'pull_requests' is "
                      "missing or not a list")
    if not entries:
        raise Refusal(f"the PR export at {path}: field 'pull_requests' lists "
                      "no pull requests")
    return repository, entries


def _label(repository: str, entry, row: int) -> str:
    number = entry.get("number") if isinstance(entry, dict) else None
    if isinstance(number, int) and not isinstance(number, bool):
        return f"{repository}#{number}"
    return f"{repository}#row{row}"


def _timestamp(value, label: str, field: str):
    """A timestamp the export carries, or None. Malformed refuses by name."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise Refusal(f"pull request {label!r}: field {field!r} is not an "
                      "ISO 8601 timestamp")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise Refusal(f"pull request {label!r}: field {field!r} is not an "
                      f"ISO 8601 timestamp: {value!r}") from exc
    return value


def _git(args, cwd, timeout):
    try:
        return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True,
                              text=True, encoding="utf-8", errors="replace",
                              timeout=timeout)
    except FileNotFoundError as exc:  # pragma: no cover - depends on the host
        raise Refusal("git not found on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError(f"git {args[0]} exceeded the time bound") from exc
    except OSError as exc:
        raise Refusal(f"the clone at {cwd} cannot be opened: {exc}") from exc


def _pr_diff(clone, merge_base, head, timeout) -> str:
    """The PR's diff, replayed from the clone's objects and nothing else.

    Read-only git plumbing with external diff drivers and textconv filters
    disabled: a clone that configures either is trying to run code, and the
    replay must never execute repository code.
    """
    result = _git(["diff", "--no-ext-diff", "--no-textconv",
                   merge_base, head, "--"], clone, timeout)
    if result.returncode != 0:
        raise Refusal(f"the clone at {clone} cannot produce the diff from "
                      f"{merge_base} to {head}: {result.stderr.strip()}")
    return result.stdout


def _require_inside_clone(clone, label: str, path) -> None:
    """Every path the replay touches stays inside the clone."""
    if not isinstance(path, str) or not path:
        raise Refusal(f"pull request {label!r}: path {path!r} is not a "
                      "repository path")
    root = Path(clone).resolve()
    parts = PurePosixPath(path).parts
    escapes = (".." in parts or PurePosixPath(path).is_absolute()
               or "\\" in path or WINDOWS_DRIVE_RE.match(path) is not None
               or not (root / path).resolve().is_relative_to(root))
    if escapes:
        raise Refusal(f"pull request {label!r}: path {path!r} leaves the clone "
                      f"at {clone}")


def _replay(clone, label: str, merge_base, head, timeout):
    """(touched_tests, checker_flagged) for one PR, from the replay alone."""
    diff_text = _pr_diff(clone, merge_base, head, timeout)
    changes, _deleted = summarize(diff_text)
    for change in changes:
        _require_inside_clone(clone, label, change.path)
    touched = any(is_test_file(change.path) for change in changes)
    flagged = bool(scan_diff(diff_text, root=str(clone)))
    return touched, flagged


def _bounded(work, seconds: float, label: str):
    """One pull request, bounded: a pathological diff cannot stall the round."""
    pool = ThreadPoolExecutor(max_workers=1)
    try:
        future = pool.submit(work)
        try:
            return future.result(timeout=seconds)
        except (TimeoutError, FutureTimeout) as exc:
            # Both, on purpose: `concurrent.futures.TimeoutError` is a distinct
            # class before Python 3.11 and an alias of the builtin after it, so
            # catching only the builtin let a slow pull request raise out of
            # `collect()` on 3.10 -- the version this project still supports.
            raise Refusal(f"pull request {label!r}: exceeded the per-PR time "
                          f"bound of {seconds} seconds") from exc
    finally:
        pool.shutdown(wait=False, cancel_futures=True)


def _collect_pr(clone, repository: str, entry, row: int, timeout: float) -> dict:
    label = _label(repository, entry, row)
    if not isinstance(entry, dict):
        raise Refusal(f"pull request {label!r}: export row is not a JSON object")
    for field in ("number", "merge_base", "head", "merged_at"):
        if field not in entry or entry[field] is None:
            raise Refusal(f"pull request {label!r}: field {field!r} is missing")
    number = entry["number"]
    if not isinstance(number, int) or isinstance(number, bool):
        raise Refusal(f"pull request {label!r}: field 'number' is not a number")
    commits = {}
    for field, role in (("merge_base", "merge base"), ("head", "head")):
        value = entry[field]
        if not isinstance(value, str) or not SHA_RE.match(value):
            raise Refusal(f"pull request {label!r}: field {field!r} is not a "
                          "commit id")
        probe = _git(["cat-file", "-e", f"{value}^{{commit}}"], clone, timeout)
        if probe.returncode != 0:
            raise Refusal(f"pull request {label!r}: {role} commit {value!r} is "
                          f"missing from the clone at {clone}")
        commits[field] = value
    merged_at = _timestamp(entry["merged_at"], label, "merged_at")
    if merged_at is None:
        raise Refusal(f"pull request {label!r}: field 'merged_at' is missing")
    flagged_at = _timestamp(entry.get("flagged_at"), label, "flagged_at")
    resolved_at = _timestamp(entry.get("resolved_at"), label, "resolved_at")
    markers = {}
    for field, out in (("override", "override"), ("opt_out", "removal_or_optout")):
        value = entry.get(field, False)
        if not isinstance(value, bool):
            raise Refusal(f"pull request {label!r}: field {field!r} is not a "
                          "boolean")
        markers[out] = value
    files = entry.get("files", [])
    if not isinstance(files, list):
        raise Refusal(f"pull request {label!r}: field 'files' is not a list of "
                      "paths")
    for path in files:
        _require_inside_clone(clone, label, path)

    touched, flagged = _replay(clone, label, commits["merge_base"],
                               commits["head"], timeout)
    return {"pr": f"{repository}#{number}", "repository": repository,
            "touched_tests": touched, "checker_flagged": flagged,
            "human_judgment": None, "merged_at": merged_at,
            "flagged_at": flagged_at, "resolved_at": resolved_at,
            "override": markers["override"],
            "removal_or_optout": markers["removal_or_optout"]}


def collect(export_path, clone_path, consent_path, out_path=None,
            per_pr_seconds: float = DEFAULT_PER_PR_SECONDS) -> list:
    """One consented repository's merged PR export, replayed into the friction
    harness's PR log. Writes the log when `out_path` is given and returns it."""
    consented = _load_consent(consent_path)
    repository, entries = _load_export(export_path)
    if repository not in consented:
        raise Refusal(f'repository "{repository}" has no recorded consent in '
                      f"{consent_path}")
    if not Path(clone_path).is_dir():
        raise Refusal(f"the clone at {clone_path} is not a directory")
    probe = _git(["rev-parse", "--is-inside-work-tree"], clone_path,
                 per_pr_seconds)
    if probe.stdout.strip() != "true":
        raise Refusal(f"the clone at {clone_path} is not a git working tree")

    records = []
    for row, entry in enumerate(entries, start=1):
        label = _label(repository, entry, row)
        records.append(_bounded(
            lambda entry=entry, row=row: _collect_pr(
                clone_path, repository, entry, row, per_pr_seconds),
            per_pr_seconds, label))
    if out_path is not None:
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
    return records


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="collector.py", description=__doc__)
    parser.add_argument("--export", required=True,
                        help="the merged PR export (hosting API metadata as JSON)")
    parser.add_argument("--clone", required=True,
                        help="the local clone holding the merge base and head commits")
    parser.add_argument("--consent", required=True,
                        help="the consent record (repositories, contact, date, scope)")
    parser.add_argument("--out", default=str(HERE / "results" / "pr-log.json"),
                        help="where to write the PR log")
    parser.add_argument("--per-pr-seconds", type=float,
                        default=DEFAULT_PER_PR_SECONDS,
                        help="the per-PR time bound (default %(default)s)")
    args = parser.parse_args(argv)
    try:
        records = collect(args.export, args.clone, args.consent,
                          out_path=args.out,
                          per_pr_seconds=args.per_pr_seconds)
    except Refusal as exc:
        print(f"collector: refused to run: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    print(f"collected {len(records)} merged pull request(s) from "
          f"{records[0]['repository']}")
    print(f"written -> {args.out}")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
