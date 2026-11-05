# Narrow `verifier-config-changed` to changes that can alter what runs

## Problem Statement

The strict gate fires `verifier-config-changed` on ordinary repository
maintenance. The ten-repository survey measured it: 104 of 109 flags across 250
commits came from this one rule, and 94 of those were GitHub workflow files and
`.pre-commit-config.yaml` — dependency bumps, action version updates, lint
configuration. In report mode that is noise next to honest work. In strict mode
each one blocks the turn until somebody writes a waiver, which is roughly one
review every 2.4 commits on a repository with active CI.

The consequence is not cosmetic. A gate that asks about every `uses:
actions/checkout@v4` bump trains its users to waive without reading, and a
waiver written without reading is exactly the "I stopped looking" state the
waiver ledger exists to distinguish from "I decided this is fine".

The rule also cannot currently claim its own technique honestly. The taxonomy's
`runner-config-tamper` row says the rule asks "when a watched config file is
touched", which is true and is the problem: what matters is not that a file was
touched but whether the change can alter what runs.

## Solution

Fire the rule when a change can change what is checked, and stay quiet when it
cannot — from the user's perspective, a CI dependency bump, an action version
update or a pre-commit `rev:` bump no longer produces a finding, while removing
a test step, loosening a runner invocation, disabling a hook or changing
`addopts` still does.

The rule id, code, severity, `requires_review` status and the "asks, never
accuses" posture do not change. Only the set of diffs that reach it narrows.
The measured target: the survey's 104 flags from this rule fall to a small
number on the same history, and every remaining flag is a change a human would
call "this could alter what runs".

## User Stories

1. As a developer with a strict gate on a repository with active CI, I want a
   Dependabot workflow bump to produce no finding, so that I only see the gate
   when it has something to say.
2. As a developer, I want an action version update (`uses: actions/setup-python@v5`
   to `@v6`) to be silent, so that routine maintenance does not need a waiver.
3. As a developer, I want a `rev:` bump in the pre-commit configuration to be
   silent, so that updating a linter's version does not read as tampering.
4. As a developer, I want a removed or disabled test step in a CI workflow to
   still raise a finding, so that "the tests stopped running" is not laundered
   by narrowing the rule.
5. As a developer, I want a `continue-on-error: true` or an `if: false` added to
   a test job to raise a finding, so that a passing checkmark that no longer
   gates anything is visible.
6. As a developer, I want a runner invocation that gains `--ignore`, `-k`,
   `--deselect`, `--no-cov` or `|| true` on a changed line to raise a finding,
   so that the common ways of shrinking a test run are still asked about.
7. As a developer, I want a pre-commit hook whose `id`, `entry`, `args`,
   `stages`, `files` or `exclude` changed to raise a finding, so that a hook
   that stops checking a path is visible.
8. As a developer, I want a pre-commit hook that was removed entirely to raise a
   finding, so that deleting a check is not silent.
9. As a developer, I want `pytest.ini`, `tox.ini` and `noxfile.py` to remain
   whole-file watchers, because those files exist to configure the runner and a
   change to them is a change to what runs.
10. As a developer, I want `.greenwash/config.json`, the hook wiring and the
    `.claude/` and `codex/hooks/` trees to remain whole-file watchers, because
    they are the gate itself.
11. As a developer, I want a dependency named something like `test-utils` or
    `testing-library` in `package.json` to be silent, so that a package name is
    not mistaken for runner configuration.
12. As a developer, I want `pyproject.toml` and `package.json` to keep firing
    when `[tool.pytest.ini_options]`, `addopts`, `testpaths`, the `test` script
    or a runner dependency actually changes.
13. As a maintainer, I want the rule's description and the README table row to
    state what it now does, so that "the files that decide what gets checked"
    is not a claim the code no longer supports.
14. As a maintainer, I want the taxonomy's `runner-config-tamper` row to
    describe the narrowed trigger, so that the coverage matrix stays honest.
15. As a maintainer, I want the ten-repository survey re-run and republished
    after the change, so that the noise reduction is a measurement rather than a
    claim.
16. As a maintainer, I want the planting benchmarks to still catch the modeled
    attacks after the change, so that narrowing did not quietly remove coverage.
17. As a maintainer, I want a negative test per silent case and a positive test
    per still-firing case, so that the rule cannot drift back into noise.
18. As a maintainer, I want the waiver policy page to keep describing this rule
    correctly, so that the review workflow and the finding agree.
19. As an agent under a strict gate, I want the rule to keep asking rather than
    accusing, so that an honest CI change never produces a conviction.
20. As an agent, I want a finding I can resolve with a waiver that names me, so
    that a genuine change is a recorded decision and not a suppressed rule.
21. As a reviewer, I want every remaining finding to name the file and say what
    changed, so that triage is a glance rather than an investigation.
22. As a reader of the benchmark summary, I want the false-positive survey
    numbers on that page to update with the new run, so that the page does not
    quote a superseded measurement.
23. As a reader of the launch post, I want its statement about the gate's noise
    to match the measurement after the fix, so that the post does not describe a
    problem that no longer exists.
24. As a future contributor, I want the narrowing to need no new rule id and no
    schema change, so that existing waivers, stored findings and JSON consumers
    keep working.

## Implementation Decisions

- **One module changes.** The verifier-config rule module owns the watched-file
  sets and the changed-line inspection. No other rule changes, and the registry
  gains no rule.
- **No contract change.** The rule id (`verifier-config-changed`), code
  (`GW-TEST-007`), category, severity (`MEDIUM`), confidence (`LOW`) and
  `requires_review=True` all stay. The emitted `Signal` shape is unchanged: one
  signal per file, carrying the path and the explanation.
- **Three tiers of watched file, replacing two:**
  1. *Whole-file watchers* — files whose purpose is runner configuration:
     `pytest.ini`, `tox.ini`, `noxfile.py`, `action.yml`,
     `.pre-commit-hooks.yaml`, `hooks/hooks.json`, and the prefixes
     `.greenwash/`, `codex/hooks/`, `.claude/`. Unchanged from today, and
     `.greenwash/waivers.json` stays exempt so writing a waiver does not open a
     finding.
  2. *Changed-line watchers* — files that mix runner configuration with ordinary
     metadata: `.github/workflows/*`, `.pre-commit-config.yaml`,
     `pyproject.toml`, `setup.cfg`, `package.json`. These fire only when the
     added or removed lines contain a runner token or a bypass token, and never
     on a version-bump line.
  3. *Ignored* — everything else.
- **Version-bump lines are excluded before token matching.** A line that matches
  an action/extension reference with a version (`uses: …@vN`, `rev: …`) or a
  plain dependency version assignment is not runner configuration, whatever else
  the line contains. This is what removes the Dependabot noise without a
  repository allowlist.
- **Runner tokens are runner-specific.** The set covers pytest, tox, nox, jest,
  vitest, mocha, ava, rspec, phpunit, `go test`, `cargo test`, `dotnet test`,
  `mvn test`, gradle test, plus configuration keys `testpaths`, `addopts`,
  `coverage`, `collect_ignore`, `deselect` and the script key `test`. The bare
  words `test` and `tests` are removed from the token set: they matched package
  names (`test-utils`) and prose, which is where the manifest false positives
  came from.
- **Bypass tokens always fire.** A changed line containing `continue-on-error`,
  `if: false`, `--ignore`, `--deselect`, `--no-cov`, `|| true`, `set +e`,
  `allow_failure` or `ignore_fail` is a finding regardless of which watch tier
  the file is in.
- **Removal counts.** Deleted lines are inspected the same way as added lines, so
  deleting the step that runs the tests is a finding.
- **The explanation says why it fired.** The signal message names what was found
  ("a test command changed", "a hook was removed", "a skip condition was added"),
  not only that a watched file changed.
- **Description and taxonomy move with the rule.** The rule's description, the
  README row, the theme's `runner-config-tamper` technique text and any page
  quoting the rule's trigger are updated in the same change. The technique's
  coverage status stays `PARTIAL`.
- **The survey is the acceptance measurement.** The ten-repository survey is
  re-run on the same repositories and the artifact, README, benchmark summary
  and interpretation page are updated with the new counts.

## Testing Decisions

A good test here states a diff and asserts what a user sees: the rule fired or
it did not, and for the cases that matter, what the finding says. It does not
reach into the watched-file sets, the token lists, or any helper — those are
implementation and may change.

The seam is the existing one: construct a real repository, change files, run the
scanner over the working tree, and assert on the returned rule ids. This is how
every other rule is tested, so no new seam is introduced.

Prior art: the rule tests in the rule suite (positive and benign-twin pairs),
the tampering benchmark's attack/twin fixtures, and the strict-gate tests that
assert a finding blocks and a waiver permits.

Behaviours pinned by tests:

- Dependabot-style workflow diff, action version bump, `rev:` bump in
  pre-commit, a dependency named `test-utils`, and a version-only manifest edit
  — all silent.
- A removed test step, `continue-on-error: true`, `if: false`, a runner command
  gaining `--ignore`/`-k`/`--no-cov`, a pre-commit `entry` change, a removed
  pre-commit hook, and a removed `addopts` line — all fire.
- The existing whole-file watchers still fire (`.greenwash/config.json`,
  `pytest.ini`, `tox.ini`).
- The tampering benchmark's two verifier-config attacks still fire, and its
  benign twins still do not.
- The rule's description in the README and the registry agree.

The survey is not a test (it needs network and ten clones); it is run once as
the acceptance measurement and its artifact is what the docs quote.

## Out of Scope

- The severity, confidence or `requires_review` status of the rule.
- Any behavioral-layer change, any new rule, any new language pack.
- A repository-specific allowlist or per-path configuration for the rule.
- The waiver UX, the strict decision table and the exit codes.
- The behavioural re-run (still blocked on a reachable model) and the push,
  tag and release (blocked on credentials in this environment).
- Re-measuring the other 5 flags in the survey; they are not this rule.

## Further Notes

The measured baseline is the survey committed with this spec: 10 repositories,
250 commits, 1,029 file changes, 109 flags, of which 104 were
`verifier-config-changed` — 94 on workflow and pre-commit files, 10 on manifests,
including two on `package.json` files under `tests/`.

The risk in narrowing is asymmetric. A rule that fires too often costs reviews;
a rule that fires too rarely costs the detection it exists for. The tests are
therefore written as pairs, and the tampering benchmark is the second opinion:
if a planted `pytest.ini` deselection stops firing, the narrowing has gone too
far. Anything the token set cannot see — a bypass written as a shell script in
a separate file, a test job replaced by a no-op with the same name — stays a
partial-coverage gap and the taxonomy continues to say so.

Nothing here touches the behavioral claim. The gate's noise and the plugin's
effect are separate measurements, and the pages that report the second one were
corrected in the previous change.
