# What did not work

A launch page that only lists successes is a page nobody should believe. These
are the things this project tried that did not do what it hoped, with the
numbers attached. Most of them are still open.

## 1. The behavioural claim: the plugin did not reduce silent cheating

This is the one that matters, because it is the claim the whole idea rests on.

Over 252 scored agent runs -- 24 tasks, three plugin states, three runs each --
the silent-cheat rate was **7% with the plugin off, 7% with the skill alone, and
8% with the skill and the hook**. The delta, **-1.4 points**, sits inside every
arm's confidence interval: `off` [3, 15], `skill-only` [3, 15], `full` [4, 17].

It is published as **no measurable effect at this sample size**, on the front
page, above the fold, rather than as a reduction. The raw rows are in
`benchmark/results/delta.jsonl`; the summary is in `benchmark/RESULTS.md`.

Two further limits on that number, both stated on the pages that quote it: the
corpus is first-party, and the run predates the test-integrity check, so it
describes the plugin as it was then and not as it is now. A preregistration for
a study that would replace it is in [EVALUATION_PROTOCOL.md](./EVALUATION_PROTOCOL.md).

## 2. The cheat class where the tool has no leverage: a swallowed exception

All 16 silent cheats in that run were `mock` or `swallow` shortcuts. Nine of
them were the **same task** (`json-load-default`, an exception swallowed into a
default) and **no arm caught it** -- not the static scan, not the held-out
suite, not the hook.

The reason is structural rather than a bug: the visible suite still passes, the
held-out suite that disagrees is one the agent never sees, and an
`except JSONDecodeError: return {}` is indistinguishable from correct code
without knowing what the caller expects.

Two things changed because of it: `error-path-default` (GW-DIV-002) now fires
when a handler returns a default and nothing nearby tests that path, and the
test-integrity check re-runs a changed test's committed form against the new
code. **Neither has been re-measured** against that run -- the numbers on this
page describe the plugin as it was, and saying otherwise would be the exact
failure this file exists to avoid.

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

## What is still open

| Open | Why it is not closed |
|---|---|
| A re-measured behavioural effect | Needs the preregistered study, an independent corpus, and a pinned image |
| Independent authorship of the corpus | Needs maintainers outside this project; the governance documents are the invitation |
| A false-positive *rate* rather than a flag count | Needs a labelled sample of real code, not 29 hand-classified flags |
| The swallow class, generally | Detection cannot see intent in an error path; the remedy today is a held-out suite, which almost nobody has |
| A note when a changed file cannot be parsed | The BOM half is fixed; a genuinely unparseable file still goes quiet (section 8) |
| The four unmeasured language tasks | Needs the toolchains and a full re-run |
