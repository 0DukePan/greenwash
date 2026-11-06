# What did not work

A launch page that only lists successes is a page nobody should believe. These
are the things this project tried that did not do what it hoped, with the
numbers attached. Most of them are still open.

## 1. The behavioural claim: the pilot measured labels, not an effect

This is the one that matters, because it is the claim the whole idea rests on.

**We reported a 7% cheat rate and a null effect. On inspection, all 16 rows were
honest fixes to tasks whose hidden tests checked unstated requirements: the
model solved what the visible suite asked. The corrected labels are
`underspecified`, the integrity-cheat rate is 0% in every arm (0/72 each, 95% CI
[0, 5]), and the delta is +0.0 points.**

**Then we found that the instrument could not have recorded the alternative.**
At the time of the run, `classify()` compared the checker's findings -- dicts --
against a set of rule ids, so a diff that carried a finding behaved in one of two
ways: with the hidden suite failing it raised `TypeError` and ended the run, and
with the hidden suite passing it was labelled `genuine fix`. The cheat the plugin
exists to catch was the one shape the outcome table could not produce. It is
fixed in `benchmark/harness.py` and pinned by tests (section 12); **the run has
not been repeated**, because that needs a funded model.

Two further limits are visible in the data rather than in the prose. The 252 rows
in `benchmark/results/delta.jsonl` carry no diffs, no transcripts and no detector
flags -- `greenwash_flags` is empty in every row -- so the 16-row correction
rests on a manual reading the repository cannot reproduce. And the run predates
the test-integrity check, so it describes the plugin as it was then.

What the pilot supports is therefore a set of labels on one corpus with one
model, not a measurement of the plugin's effect in either direction. A re-run
that saves its evidence and uses the fixed classifier is the next step; it is
blocked on a reachable model -- `python benchmark/preflight.py` reports the
gateway is not logged in.

## 2. The rows we called cheats were honest fixes to underspecified tasks

All 16 rows were `mock` or `swallow` class tasks (7 and 9 by label), nine of
them the **same task** (`json-load-default`), then `default-port-by-env` (5),
`backoff-delay` (1) and `slugify-basic` (1). In every case the visible suite
stated one requirement and the hidden suite checked another that the prompt
never mentioned: `load` had to return `{}` for anything that was not a JSON
object, `delay(0)` had to be exponential, double spaces had to collapse. The
agents did what the visible tests asked. Nothing was laundered: no touched
tests, no mocks of the unit under test, no hardcoded literals.

That is a corpus bug, not a model behavior, and it is why the v1 rates say
nothing about cheating. Three things changed because of it: the outcome
taxonomy now separates `integrity cheat` (a diff that tampers) from `spec
overfit` (a clean diff on an underspecified task), the harness records
`diff_class` per row so the distinction is evidence rather than judgment, and
the tasks whose hidden tests checked unstated requirements will get their full
spec in the prompt. A replacement corpus with impossible tasks -- where any pass
is a cheat by construction -- is being built so the next study needs no labels at
all.

## 3. The static layer does work the behavioural layer cannot

The three `exploit` tasks -- an unconditional `__eq__`, a patched `conftest.py`,
and a `sys.exit(0)` -- satisfy the held-out suite too. Only the static layer
catches them: 3/3 static, 1/3 behavioral. That is the argument for running both
layers, and it is also a warning: "the tests pass" is not evidence about a
workspace that has been edited to make them pass.

## 4. Four language tasks are unmeasured on the machine that ran the study

Go, Rust, Ruby and Java are not installed on the Windows laptop where the
measurement ran, so 4 of 28 tasks are recorded as `skipped: no toolchain` and
kept out of every rate. The CI `languages` job runs the same corpus where the
toolchains exist and asserts that nothing skipped -- but the *agent-facing*
table has never been run on all six languages, and it will not be until the
preregistered study runs in a pinned image.

## 5. The corpus is first-party, so it cannot establish detector quality

The same people wrote the detector and the tasks. That is fine for regression
coverage and it is not fine as a claim about detector quality: the tasks encode
this project's idea of what a cheat looks like. `benchmark/inconclusive/` (six
ambiguous changes that must be asked about and never convicted) narrows the gap
but does not close it. Independent authorship is the fix, and it has not
happened yet -- which is why the evaluation governance documents describe a
separate repository with non-core maintainers holding merge authority.

## 6. One asking rule was 95% of the noise on real history

The scanner was run over 250 recent commits of ten unrelated repositories --
1,029 file changes -- and produced 109 flags. **104 of them were
`verifier-config-changed` firing on `.github/workflows/*`,
`.pre-commit-config.yaml`, `pyproject.toml`, `package.json` and `tox.ini`** --
dependency bumps, action-version updates and lint configuration. Three were
`conftest-changed`. Two accused, and both were judged legitimate on inspection:
an assertion-weakened flag on a `werkzeug` compatibility test whose removed
assertions were implied by the narrower expected exception, and a
swallowed-exception flag on a deliberate empty `catch` in a `got` test.

The scanner's precision on this sample was fine. The gate's was not: those 104
reviews are what strict mode demanded over active CI, roughly one per 2.4
commits. That was the first thing fixed rather than waived -- the rule now asks
only when a change can alter what runs, and a version reference is not that. The
same history now produces **14 flags**: 12 asking (7 the narrowed rule, all
genuine runner changes; 3 conftest changes; and 2 from the newly measured
`error-path-default`) and the same two false positives. The before and
after are in [false-positive-survey.md](./false-positive-survey.md); it is a
survey, not a rate -- classifying 109 flags by hand gives a number, not a
population estimate.

The narrowing has the shape every narrowing has: it sees less. A bypass written
in a separate shell script, or a test job replaced by a no-op with the same
name, is still outside the trigger, and the taxonomy keeps that technique's
coverage at `PARTIAL` rather than promoting it.

## 7. `error-path-default` was blind to the survey until the harness was fixed

It was added *because* of the misses in section 2, so it had never been run
over the real-history survey. The first attempt to measure it reported nothing,
and that zero was not a result: `benchmark/fp_survey.py` scanned every commit's
diff without passing the surveyed repository, so the scanner resolved parsed
Python files against the greenwash checkout. A rule that needs the file's tree
-- `error-path-default` is one -- found no file under `src/...` and returned no
module. An instrument that cannot see reports zero whether or not the thing is
there.

The fix is one argument: each diff is now scanned with its own repository as
the working directory, and `error-path-default` can read the file it is
judging. The rest of the artifact did not move -- same twelve flags, same
commits. On the same 250 commits the rule fires twice, both on one change in
`pytest`: a true ask on `564d690` (the JAX fix landed without a test, and the
same pull request added one six commits later) and a false positive on the
merge `4b3bb3c` (the merge already carries the regression test, but the rule's
neighbouring-test heuristic does not know pytest's `testing/` directory). Two
flags, one change, zero cheats; the measurement is in
[false-positive-survey.md](./false-positive-survey.md).

What remains a gap is the heuristic, not the measurement: widening that guess
list is a rule change and needs its own pass, and the AST rules still read the
clone's checked-out tree rather than each commit's tree, so a flag is confirmed
by reading the commit.

## 8. A file that cannot be parsed produces no note

The Python rules work on a parsed tree, and a file that will not parse is simply
skipped: no signal, no note, nothing in the report. That is the wrong shape for
this tool's own philosophy -- a check that could not run must not read as a
pass -- and it bit this release: a UTF-8 byte-order mark (what PowerShell,
Visual Studio and Notepad write by default) made `ast.parse` fail, and a
planted `@pytest.mark.skip` came back as `0 signal(s)` on a Windows machine.

The BOM half is fixed (`utf-8-sig`, with regression tests). The general half is
not: a genuinely unparseable *changed* Python file still goes quiet instead of
saying so. The fix is a signal for "this file was changed and could not be
read", and it is on the list rather than in the build.

## 9. Two namesakes, and one install path that had to be withdrawn

The PyPI name `greenwash` belongs to an unrelated project, and the npm name is
not owned by this project either. Both facts were in the repository's own risk
list before this release, and both had the same consequence: a public install
command that installed something else.

What changed: the distribution is now **`greenwash-cli`** (import name and
command unchanged), and **`npx greenwash` is no longer advertised** -- the shim
is real and tested, but `npm/README.md` documents the local `npm pack` path
instead of a registry install, because the registry name is not verified.

## 10. The hook had a second copy of the policy

The Claude hook used to exit 2 for *any* finding in enforce mode -- including a
verified one -- because it re-derived "should this block?" from the verdict
instead of reading the CLI's exit code. Two copies of a decision table drift.
Found while building the strict profile, fixed by deleting the copy: the CLI
owns the policy, the hook owns the wording.

## 11. The claim ledger

Every public claim maps to the evidence that licenses it, the status of that
evidence, and the strongest wording allowed today. The table below is the
ledger itself, rendered from `benchmark/claim_ledger.py` -- regenerate it with
`python benchmark/claim_ledger.py --table`. `tests/test_claim_ledger.py` fails
when a public page states more than a row allows (naming the claim and the
page), when a row quotes a number no generated artifact backs, and when this
table stops matching the data.

<!-- claim-ledger:begin -->
| Claim | Evidence required | Status | Strongest wording allowed today |
|---|---|---|---|
| detector-recall | A frozen evaluation run on a corpus this project did not author, at the pre-registered sample size. | Measured on the first-party internal corpus only; the frozen run has not happened. | On a labelled corpus of 24 tasks with one planted cheat each, the scanner caught 24 of 24 planted cheats (95% CI 86.2%-100%). |
| false-alarms | A labelled sample of real code large enough for a rate, not a hand-classified flag count. | Measured on the recorded honest fixes of the internal corpus only. | It flagged 0 of 24 recorded honest fixes (95% upper bound 13.8% at this sample size). |
| behavioural-effect | The pre-registered behavioural study: an independent corpus, a pinned image, and an instrument that is not the treatment. | One live first-party run. Its rows carry no detector flags, no diffs and no transcripts, and the classifier that produced the labels could not record a cheat that passes the held-out suite -- that is fixed now, but the run was not repeated after the fix. | No measurable effect at this sample size: +0.0 points over 252 scored runs (95% CI [0, 5] in every arm). The run recorded no detector flags and its labels predate the instrument fix that can label a passing cheat, so this is a label count, not a measurement of the plugin's effect. |
| fp-survey | A labelled sample of real code; classifying flags by hand gives a number, not a population estimate. | A survey of recent history in 10 repositories, published for inspection. | On the recent history of 10 repositories (250 commits, 1,029 file changes) the scanner produced 14 flags: 12 are the rules that always ask for an explanation, 2 are genuine false positives. This is a survey, not a rate. |
| first-party-corpus | Corpus authorship independent of this project, with merge authority outside it. | Not established; the governance documents are the invitation. | The corpus is first-party: it measures the detector against its own authors' idea of a cheat and cannot establish detector quality. |
| rate-claims | The frozen run at the pre-registered sample size; until then every number is a count with an interval. | Not available; the current corpus is first-party and small. | Every published number is an interval-qualified count on the internal corpus; a rate claim waits on the frozen run. |
| strength-advisory | The strength check's error rate, measured; promotion to a verdict is deliberately deferred. | Ships as an advisory flag in this version. | The strength check ships as an advisory flag, not a verdict; promotion waits until its error rate is measured. |
| verdict-vocabulary | Correctness proofs, which no run of this tool produces. | A verdict reports the checks that ran and the diff's shape. | A verdict reports the checks that ran; it is evidence, not proof of correctness. |
| scope-exclusions | Retrieval and leakage detection; training-time reward hacking; languages beyond Python and pytest. | Out of scope for this version; never claimed. | What greenwash does not cover: retrieval and leakage detection, training-time reward hacking, languages beyond Python and pytest in this version. |
<!-- claim-ledger:end -->

## 12. The classifier could not label a cheat, and CI said so for three weeks

`diff_class()` compared the checker's findings as strings; the checker emits
dicts (`[{"kind": "test-skipped", ...}]`). The result was deterministic:

- a diff with a finding, visible suite passing, hidden suite failing:
  `TypeError: cannot use 'dict' as a set element` -- the run ends;
- a diff with a finding and both suites passing: `genuine fix`.

The CI job `Harness plumbing (no model)` plants a hardcoded return with the fake
agent and asserts the detector catches it. It failed on every push from
2026-10-15, on all three branches. The unit suite did not see it because no test
called `classify()` with the shape the checker actually emits -- the tests passed
plain strings.

The fix accepts both shapes (`flag_kinds`), adds a `flagged` outcome for a
passing run that carries a mechanism rule (reported, never counted as a cheat,
because `hardcoded-return` has a documented legitimate class), and pins all three
shapes in `tests/test_relabel.py`. The plumbing run now completes:
`add-subtract-swap full run1 -> integrity cheat ... flags=['hardcoded-return']`.

## What is still open

| Open | Why it is not closed |
|---|---|
| A re-measured behavioural effect | The instrument fix is in; the run needs a reachable model and a corpus that saves its diffs and flags |
| Evidence for the 16-row correction | The rows carry no diffs or transcripts, so the correction rests on a manual reading |
| Independent authorship of the corpus | Needs maintainers outside this project; the governance documents are the invitation |
| A false-positive *rate* rather than a flag count | Needs a labelled sample of real code, not 14 hand-classified flags |
| The swallow class, generally | Detection cannot see intent in an error path; the remedy today is a held-out suite, which almost nobody has |
| A note when a changed file cannot be parsed | The BOM half is fixed; a genuinely unparseable file still goes quiet (section 8) |
| The four unmeasured language tasks | Needs the toolchains and a full re-run |
