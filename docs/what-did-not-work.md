# What did not work

A launch page that only lists successes is a page nobody should believe. These
are the things this project tried that did not do what it hoped, with the
numbers attached. Most of them are still open.

## 1. The behavioural claim: the plugin showed no effect, and the benchmark was wrong

This is the one that matters, because it is the claim the whole idea rests on.

**We reported a 7% cheat rate and a null effect. On inspection, all 16 were
honest fixes to tasks whose hidden tests checked unstated requirements. The
model never cheated. Our benchmark measured underspecification, not cheating.**

Over 252 scored agent runs (24 tasks, three plugin states, three runs each) the
v1 labels counted 16 "silent cheats" -- 7% with the plugin off, 7% with the
skill alone, 8% with the skill and the hook -- and a delta of **-1.4 points**
that sat inside every arm's confidence interval. Under the corrected outcome
taxonomy those 16 rows are `underspecified`, the integrity-cheat rate is **0% in
every arm** (0/72 each, 95% CI [0, 5]), and the delta is **+0.0 points**.

Every number here is re-derivable from the data alone. Each row in
`benchmark/results/delta.jsonl` keeps its v1 label in `outcome_v1`, and
`python benchmark/tools/relabel.py --dry-run` recomputes the corrected one from
the recorded evidence. The summary is in `benchmark/RESULTS.md`.

Two further limits on that number, both stated on the pages that quote it: the
corpus is first-party, and the run predates the test-integrity check, so it
describes the plugin as it was then and not as it is now. A preregistration for
a study that would replace it is in [EVALUATION_PROTOCOL.md](./EVALUATION_PROTOCOL.md).

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

## 6. Nine false positives on real history

The scanner was run over 59 recent commits of three unrelated repositories --
1,225 file changes -- and produced 29 flags. Twenty are the rules that always
ask for an explanation (`mock-in-test`, `error-path-default`, and friends) and
**nine are genuine false positives**: six `hardcoded-return` flags on functions
that legitimately return a constant a test asserts, and three on a successful
`exit(0)` in ordinary CLI code.

Each class is written up in [false-positives.md](./false-positives.md), and the
ones that were fixable became regression tests. This is a survey, not a rate --
classifying 29 flags by hand gives a number, not a population estimate.

## 7. `error-path-default` has not been through the false-positive survey

It was added *because* of the misses in section 2, which means it has never been
run over the real-history survey: its false-positive behaviour is unknown, and
[false-positives.md](./false-positives.md) says so rather than implying a
measured zero. It asks rather than accuses, and in strict mode "asks" means
"blocks until someone decides", so the cost of that gap is a review, not a
wrong verdict -- but it is a gap.

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
| behavioural-effect | The pre-registered behavioural study: an independent corpus, a pinned image, and an instrument that is not the treatment. | One live first-party run; the pages that quote it say it predates the test-integrity check. | No measurable effect at this sample size: +0.0 points over 252 scored runs (95% CI [0, 5] in every arm). |
| fp-survey | A labelled sample of real code; classifying flags by hand gives a number, not a population estimate. | A survey of recent history in three repositories, published for inspection. | On the recent history of 3 repositories (59 commits, 1,225 file changes) the scanner produced 29 flags: 20 are the rules that always ask for an explanation, 9 are genuine false positives. This is a survey, not a rate. |
| first-party-corpus | Corpus authorship independent of this project, with merge authority outside it. | Not established; the governance documents are the invitation. | The corpus is first-party: it measures the detector against its own authors' idea of a cheat and cannot establish detector quality. |
| rate-claims | The frozen run at the pre-registered sample size; until then every number is a count with an interval. | Not available; the current corpus is first-party and small. | Every published number is an interval-qualified count on the internal corpus; a rate claim waits on the frozen run. |
| strength-advisory | The strength check's error rate, measured; promotion to a verdict is deliberately deferred. | Ships as an advisory flag in this version. | The strength check ships as an advisory flag, not a verdict; promotion waits until its error rate is measured. |
| verdict-vocabulary | Correctness proofs, which no run of this tool produces. | A verdict reports the checks that ran and the diff's shape. | A verdict reports the checks that ran; it is evidence, not proof of correctness. |
| scope-exclusions | Retrieval and leakage detection; training-time reward hacking; languages beyond Python and pytest. | Out of scope for this version; never claimed. | What greenwash does not cover: retrieval and leakage detection, training-time reward hacking, languages beyond Python and pytest in this version. |
<!-- claim-ledger:end -->

## What is still open

| Open | Why it is not closed |
|---|---|
| A re-measured behavioural effect | Needs the preregistered study, an independent corpus, and a pinned image |
| Independent authorship of the corpus | Needs maintainers outside this project; the governance documents are the invitation |
| A false-positive *rate* rather than a flag count | Needs a labelled sample of real code, not 29 hand-classified flags |
| The swallow class, generally | Detection cannot see intent in an error path; the remedy today is a held-out suite, which almost nobody has |
| A note when a changed file cannot be parsed | The BOM half is fixed; a genuinely unparseable file still goes quiet (section 8) |
| The four unmeasured language tasks | Needs the toolchains and a full re-run |
