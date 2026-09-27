"""The entry point. Zero-config: `greenwash` with no arguments prints a report.

Exit codes are the whole safety story, so they are stated once, here:

    report mode (default)   0 whenever it produces a report, 3 when it cannot
                            (not a repository, or one with no commits) --
                            greenwash never fails your build unless you ask
                            it to; the report is the product
    scan / verify           0 clean, 1 findings, 3 could not run
    --enforce               0 verified, 1 not verified, 2 suspicious,
                            3 could not check (VERIFICATION_FAILED)
    --fail-on VERDICTS      the same codes, for exactly the verdicts named;
                            it implies --enforce and replaces the policy
    --strict                the same codes again, under a longer table: a
                            requires_review finding blocks until it is waived,
                            and ignore_rules is refused rather than honoured

`--enforce` is never implied. A tool that starts blocking work by default is a
tool people uninstall. `--fail-on` is an explicit policy rather than a louder
default: it names the verdicts that block, and nothing else does. `--strict`
is that same idea taken one step further -- see `greenwash/strict.py` for the
table -- and it is what the Claude and Codex plugins run.
"""

from __future__ import annotations

import argparse
import os
import sys

from . import __version__, config as config_mod, gitutil, scan as scan_mod
from . import strict as strict_mod, waivers as waivers_mod
from .doctor import doctor, initialize
from .domain import Claim, Run, TrustReport, Verdict
from .report import render, terminal
from .verify import engine as verify_engine

EXIT_OK, EXIT_FINDINGS, EXIT_BLOCKED, EXIT_ERROR = 0, 1, 2, 3

EPILOG = """exit codes:
  report mode (default) 0 whenever a report is produced, 3 when it cannot be
  --enforce returns 1 (not verified), 2 (suspicious), 3 (could not check)
  --strict  does the same, and also blocks on a finding nobody has waived

greenwash reads your diff, runs your tests, and reports what the claim is worth.
It never modifies your code, never calls a model, and never leaves your machine.
"""


def _emit(text: str, machine: bool = False) -> None:
    """Write output that survives a cp1252 console and a pipe alike."""
    if machine:
        buffer = getattr(sys.stdout, "buffer", None)
        if buffer is not None:
            buffer.write(text.encode("utf-8", "replace"))
            buffer.flush()
            return
    sys.stdout.write(terminal.encode_safe(text))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="greenwash",
        description="Report on what an agent's \"done\" claim is actually worth.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=EPILOG)
    parser.add_argument("--version", action="version", version=f"greenwash {__version__}")

    sub = parser.add_subparsers(dest="cmd")

    def common(target, verify_opts=True):
        target.add_argument("--json", action="store_true", help="versioned JSON report")
        target.add_argument("--format", choices=["terminal", "json", "markdown"],
                            default="terminal", help="output format")
        target.add_argument("--quiet", action="store_true", help="one line")
        target.add_argument("--verbose", action="store_true", help="full evidence")
        colours = target.add_mutually_exclusive_group()
        colours.add_argument("--color", dest="color", action="store_true",
                             help="force colour even when piped")
        colours.add_argument("--no-color", dest="color", action="store_false",
                             help="never colourise")
        target.set_defaults(color=None)      # None = decide from the stream
        target.add_argument("--staged", action="store_true", help="analyse staged changes only")
        target.add_argument("--base", default=None, help="diff against this ref")
        target.add_argument("--claim", default="", help="what the agent said it did")
        target.add_argument("--agent", default="", help="who made the change")
        if verify_opts:
            target.add_argument("--auto", action="store_true",
                                help="discover the test command and compare to the baseline")
            target.add_argument("--run-tests", default=None, help="test command to run")
            target.add_argument("--heldout", default=None,
                                help="path to (or command running) a suite the agent never saw")
            target.add_argument("--timeout", type=int, default=None)
            target.add_argument("--require", action="append", default=None,
                                metavar="TEXT[ => TARGET]",
                                help="something the claim says it did, optionally bound to a "
                                     "test id or `cmd: <command>` with `=>`; repeatable")
            target.add_argument("--enforce", action="store_true",
                                help="opt in to blocking exit codes")
            target.add_argument("--strict", action="store_true",
                                help="block on an unexplained finding, honouring only "
                                     "a current waiver; refuses ignore_rules")
            target.add_argument("--fail-on", default=None, metavar="VERDICTS",
                                help="comma-separated verdicts that block "
                                     "(e.g. not_verified,suspicious); implies --enforce")

    # the default action: a bare `greenwash` prints the report
    common(parser)

    for name, help_text in (("report", "produce a trust report (the default)"),
                            ("scan", "static diff analysis only"),
                            ("verify", "behavioral verification only")):
        target = sub.add_parser(name, help=help_text)
        common(target)

    init = sub.add_parser("init", help="detect, write .greenwash/config.json, and say what was found")
    init.add_argument("--json", action="store_true")

    doc = sub.add_parser("doctor", help="diagnose the environment greenwash needs")
    doc.add_argument("--json", action="store_true")

    rules = sub.add_parser("rules", help="list the rules and what they mean")
    rules.add_argument("--json", action="store_true")

    waive = sub.add_parser(
        "waive", help="record an auditable waiver for one finding, in .greenwash/waivers.json")
    waive.add_argument("--rule", required=True,
                       help="rule id or code, e.g. GW-DIV-002 or error-path-default")
    waive.add_argument("--path", required=True, help="the file the finding is in")
    waive.add_argument("--reason", required=True,
                       help="why this finding is acceptable -- a sentence, not a word")
    waive.add_argument("--reviewer", required=True, help="who decided, e.g. @maintainer")
    waive.add_argument("--expires", required=True, metavar="YYYY-MM-DD",
                       help=f"when the decision lapses (max {waivers_mod.MAX_LIFETIME_DAYS} days)")
    waive.add_argument("--fingerprint", default="",
                       help="the finding's sha256 -- taken from the current diff when omitted")
    waive.add_argument("--id", dest="waiver_id", default="", help="override the generated id")
    waive.add_argument("--base", default=None, help="diff against this ref")
    waive.add_argument("--staged", action="store_true", help="consider staged changes only")
    return parser


def _parse_fail_on(raw: str) -> list:
    """Verdict names for `--fail-on`, validated against the enum.

    Raises ValueError on a name that is not a verdict, so a typo fails loudly
    instead of silently leaving the gate open -- a policy that quietly does
    nothing is worse than one that refuses to start.
    """
    known = {verdict.value.lower(): verdict.value for verdict in Verdict}
    chosen = []
    for name in (raw or "").replace(" ", "").split(","):
        name = name.lower()
        if not name:
            continue
        if name not in known:
            raise ValueError(name)
        chosen.append(known[name])
    return chosen


def collect(args) -> tuple:
    """(report, exit_code)."""
    config = config_mod.load(".")

    fail_on = None
    raw_fail_on = getattr(args, "fail_on", None)
    if raw_fail_on:
        try:
            fail_on = _parse_fail_on(raw_fail_on)
        except ValueError as exc:
            known = ", ".join(verdict.value.lower() for verdict in Verdict)
            print(f"greenwash: unknown verdict in --fail-on: {exc.args[0]!r} "
                  f"(known verdicts: {known})", file=sys.stderr)
            return None, EXIT_ERROR

    strict = bool(getattr(args, "strict", False)) or config.strict
    if strict:
        mode = config_mod.STRICT_MODE
    elif (getattr(args, "enforce", False) or fail_on is not None or config.enforcing):
        mode = "enforce"
    else:
        mode = "report"

    claimed = getattr(args, "cmd", None)
    want_scan = claimed in (None, "report", "scan")
    want_verify = claimed in (None, "report", "verify")

    try:
        diff = gitutil.diff(staged=getattr(args, "staged", False),
                            base=getattr(args, "base", None))
    except gitutil.GitError as exc:
        print(f"greenwash: {exc}", file=sys.stderr)
        return None, EXIT_ERROR

    signals = scan_mod.scan_diff(diff) if want_scan else []
    changes, _ = scan_mod.summarize(diff)
    notes = list(config.problems)
    ignored = set(config.get("ignore_rules") or [])
    if ignored and strict:
        # Strict mode refuses to honour a suppression: the findings stay in the
        # report, so the team can see exactly what the ignore_rules were
        # hiding, and the gate blocks on the refusal. Waiving the individual
        # finding is the supported path.
        pass
    elif ignored:
        suppressed = sorted({s.rule_id for s in signals if s.rule_id in ignored})
        signals = [s for s in signals if s.rule_id not in ignored]
        if suppressed:
            notes.append(f"suppressed by config.ignore_rules: {', '.join(suppressed)}")
    if gitutil.is_subdirectory():
        notes.append(f"analysed only what changed under {os.getcwd()}; run greenwash from "
                     "the repository root for a whole-repo report")

    verification = None
    requirements: list = []
    if want_verify:
        explicit = bool(getattr(args, "run_tests", None) or getattr(args, "heldout", None)
                        or getattr(args, "require", None))
        # Zero configuration means the behavioral layer runs: find the test
        # command and compare the working tree against the committed baseline.
        # Naming a command, naming a held-out suite, or setting auto_verify is
        # how a user opts out -- and `greenwash verify` is a request to verify
        # even when those are absent.
        configured = config.explicit & {"test_command", "heldout", "auto_verify"}
        auto = (bool(getattr(args, "auto", False)) or bool(config.get("auto_verify"))
                or (not explicit and (claimed == "verify" or not configured)))
        if explicit or auto:
            outcome = verify_engine.verify(
                run_tests=getattr(args, "run_tests", None) or config.get("test_command"),
                heldout=getattr(args, "heldout", None) or config.get("heldout"),
                auto=auto,
                timeout=getattr(args, "timeout", None) or config.get("timeout") or 120,
                changed_paths=[c.path for c in changes],
                changes=changes,
                integrity=bool(config.get("test_integrity")),
                integrity_max=int(config.get("test_integrity_max") or 3),
                requirements=(getattr(args, "require", None)
                              or config.get("requirements")))
            verification = outcome.result
            signals.extend(outcome.signals)
            requirements = outcome.requirements

    ledger = waivers_mod.load(".")
    notes.extend(ledger.problems)
    application = waivers_mod.apply(signals, ledger)

    run = Run(
        agent=getattr(args, "agent", "") or config.get("agent") or os.environ.get(
            "GREENWASH_AGENT", ""),
        branch=gitutil.branch(), head_commit=gitutil.head_commit(),
        mode=mode, changed_files=changes, claim=Claim(text=getattr(args, "claim", ""),
                                                      source="cli"))
    report = TrustReport.build(run=run, signals=application.signals,
                               verification=verification, requirements=requirements,
                               notes=notes + (
                                   verification.notes if verification else []),
                               waivers=[row.to_dict() for row in application.rows])

    if mode == config_mod.STRICT_MODE:
        if fail_on is not None:
            report.notes.append("--fail-on was given alongside a strict profile and is "
                                "ignored: strict blocks on its own policy")
        gate = strict_mod.decide(report, application.rows, ignored, ledger.problems)
        report.gate = gate.to_dict()
        return report, gate.exit_code
    if mode == "enforce":
        return report, _enforced_exit(report, config, fail_on)
    if claimed in ("scan", "verify"):
        return report, EXIT_FINDINGS if report.signals else EXIT_OK
    return report, EXIT_OK


def _enforced_exit(report: TrustReport, config, fail_on=None) -> int:
    """The enforce-mode exit code, per the contract in the module docstring.

    Each kind of doubt keeps its own code: evidence that the claim does not
    hold (1), a pattern with nothing verified (2), a check that could not run
    at all (3). Collapsing any two of them would be the exact conflation this
    tool exists to catch.
    """
    if fail_on is None:
        # The shipped policy: a pattern with nothing verified always blocks,
        # and `block_on` adds the verdicts that also do. Stated in the module
        # docstring, and unchanged by --fail-on's existence.
        if report.verdict == Verdict.SUSPICIOUS.value:
            return EXIT_BLOCKED
        blocking = config.get("block_on") or ["NOT_VERIFIED", "VERIFICATION_FAILED"]
    else:
        # An explicit --fail-on replaces the policy rather than adding to it:
        # a list that still blocked a verdict it did not name would be a policy
        # the user cannot read off their own command line.
        blocking = fail_on
    if report.verdict in blocking:
        if report.verdict == Verdict.VERIFICATION_FAILED.value:
            return EXIT_ERROR
        if report.verdict == Verdict.SUSPICIOUS.value:
            return EXIT_BLOCKED
        return EXIT_FINDINGS
    return EXIT_OK


def _run_waive(args) -> int:
    """`greenwash waive`: write one decision into .greenwash/waivers.json.

    The fingerprint is the part worth getting right, so it is not typed by
    hand when it does not have to be: the finding is located in the current
    diff by rule and path, and the digest comes from the signal itself. When
    more than one finding matches, the command refuses and lists the
    candidates rather than guessing which one the reviewer meant -- a waiver
    against the wrong line is exactly the thing this is supposed to prevent.
    """
    import json

    rules = waivers_mod.known_rules()
    rule = str(args.rule or "").strip()
    if rule not in rules:
        known = ", ".join(sorted({r for r in rules if r.startswith("GW-")}))
        print(f"greenwash: unknown rule {rule!r} (known codes: {known})", file=sys.stderr)
        return EXIT_ERROR
    code = rules[rule]
    path = str(args.path or "").strip().replace("\\", "/")

    digest = str(args.fingerprint or "").strip()
    if not digest:
        try:
            diff = gitutil.diff(staged=getattr(args, "staged", False),
                                base=getattr(args, "base", None))
        except gitutil.GitError as exc:
            print(f"greenwash: {exc}", file=sys.stderr)
            return EXIT_ERROR
        candidates = [s for s in scan_mod.scan_diff(diff)
                      if s.code == code and s.path == path]
        if not candidates:
            print(f"greenwash: no {rule} finding for {path} in the current diff -- "
                  "run `greenwash scan --verbose` to see what is there.", file=sys.stderr)
            return EXIT_ERROR
        if len(candidates) > 1:
            print(f"greenwash: {len(candidates)} {rule} findings in {path}; "
                  "pass --fingerprint with the one you mean:", file=sys.stderr)
            for signal in candidates:
                where = f":{signal.line}" if signal.line else ""
                print(f"  {waivers_mod.fingerprint(signal)}  {path}{where}",
                      file=sys.stderr)
            return EXIT_ERROR
        digest = waivers_mod.fingerprint(candidates[0])

    ledger = waivers_mod.load(".")
    waiver = waivers_mod.Waiver(
        id=str(args.waiver_id or "").strip() or waivers_mod.next_id(ledger.waivers),
        rule_id=code,
        signal_fingerprint=digest,
        path=path,
        reason=str(args.reason or "").strip(),
        reviewer=str(args.reviewer or "").strip(),
        created_at=waivers_mod.iso(waivers_mod.utc_now()),
        expires_at=str(args.expires or "").strip(),
    )
    problems = waiver.problems(rules)
    if problems:
        for problem in problems:
            print(f"greenwash: {problem}", file=sys.stderr)
        return EXIT_ERROR

    written = waivers_mod.save(
        waivers_mod.Ledger(path=ledger.path, waivers=[*ledger.waivers, waiver]), ".")
    _emit(json.dumps(waiver.to_dict(), indent=2) + "\n")
    _emit(f"wrote {written}\n")
    _emit("this finding is now reported as waived with review, never as clean.\n")
    return EXIT_OK


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    command = getattr(args, "cmd", None)

    if command == "init":
        activation = initialize(".")
        if getattr(args, "json", False):
            _emit(f'{{"config": "{activation.config_path}", '
                  f'"ok": {str(activation.ok).lower()}}}\n', machine=True)
        else:
            _emit("greenwash: setting up this repository\n\n")
            _emit(activation.report(terminal.marks()) + "\n")
            _emit(f"\nwrote {activation.config_path}\n")
            _emit("report mode is on: greenwash will describe, not block.\n")
        return EXIT_OK if activation.ok else EXIT_ERROR

    if command == "doctor":
        result = doctor(".")
        if getattr(args, "json", False):
            import json
            _emit(json.dumps([check.__dict__ for check in result.checks], indent=2) + "\n",
                  machine=True)
        else:
            _emit("greenwash doctor\n\n")
            _emit(result.report(terminal.marks()) + "\n")
            if not result.ok:
                _emit("\nsomething above needs fixing before the hook can help.\n")
        return EXIT_OK if result.ok else EXIT_FINDINGS

    if command == "rules":
        import json
        rules = [{"id": rule.id, "code": rule.code, "title": rule.title,
                  "category": rule.category, "severity": rule.severity,
                  "confidence": rule.confidence, "requires_review": rule.requires_review,
                  "description": rule.description, "remediation": rule.remediation}
                 for rule in scan_mod.RULES]
        if getattr(args, "json", False):
            _emit(json.dumps(rules, indent=2) + "\n", machine=True)
        else:
            _emit(f"{'code':<12}{'rule':<24}{'severity':<10}review   what it means\n")
            for rule in rules:
                review = "yes" if rule["requires_review"] else ""
                _emit(f"{rule['code']:<12}{rule['id']:<24}{rule['severity']:<10}"
                      f"{review:<9}{rule['description']}\n")
        return EXIT_OK

    if command == "waive":
        return _run_waive(args)

    report, code = collect(args)
    if report is None:
        return code

    fmt = "json" if getattr(args, "json", False) else getattr(args, "format", "terminal")
    _emit(render(report, fmt=fmt, color=getattr(args, "color", None),
                 verbose=getattr(args, "verbose", False),
                 quiet=getattr(args, "quiet", False)), machine=fmt in ("json", "markdown"))
    return code


if __name__ == "__main__":
    sys.exit(main())
