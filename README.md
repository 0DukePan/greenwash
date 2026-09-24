<p align="center">
  <img src="assets/logo.svg" width="76" alt="greenwash">
</p>

<h1 align="center">greenwash</h1>

<p align="center"><strong>A trust report on what a coding agent's "done" actually means.</strong></p>

<p align="center">
  <a href="https://github.com/0DukePan/greenwash/actions/workflows/ci.yml"><img src="https://github.com/0DukePan/greenwash/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT"></a>
  <img src="https://img.shields.io/badge/python-3.10%2B-blue.svg" alt="python 3.10+">
  <img src="https://img.shields.io/badge/dependencies-none-brightgreen.svg" alt="no dependencies">
  <img src="https://img.shields.io/badge/schema-v1-informational.svg" alt="schema v1">
  <a href="https://github.com/0DukePan/greenwash/releases"><img src="https://img.shields.io/badge/version-0.4.1-orange.svg" alt="0.4.1"></a>
</p>

<p align="center">
  <strong>24/24 planted cheats caught &middot; 0 false positives on 24 real fixes &middot; 293 tests</strong><br>
  <sub>
    An agent under pressure to show green will skip the test, mock the unit under
    test, hardcode the expected value, or swallow the exception that would have
    failed loudly. All four produce the same visible result: a passing suite.
    greenwash reads the diff <em>and</em> runs the tests, then reports what the
    claim is worth -- with the evidence, and an honest "I could not tell" when
    there is none.
  </sub>
</p>

<p align="center">
  <strong>The part that did not work.</strong><br>
  <sub>
    Those are detector numbers. The claim underneath them is that catching a fake
    pass <em>changes what the agent does</em> -- and over 252 measured agent runs
    it did not: 7% of runs shipped a silent cheat with the check off, 8% with it
    fully on. That is -1.4 points, with every arm's interval overlapping every
    other arm's, and it is published here as the null it is rather than as a win.
    The cheat class where greenwash has no leverage is named in
    <a href="#numbers">Numbers</a>.
  </sub>
</p>

<p align="center">
  <img src="assets/demo.gif" width="720" alt="An agent 'fixes' a failing test by hardcoding the answer; greenwash reports visible tests 1/1 passing, held-out checks 0/1 failing, and a verdict of NOT_VERIFIED">
  <br>
  <sub><code>python demo/run_demo.py --terse</code> -- everything inside the terminal is verbatim output, scrolled by the generator because the report is taller than the window. The kicker above it is the one added line.</sub>
</p>

---

## Why this exists

An agent that says "done, tests pass" is making a claim. Usually it's true.
Sometimes the suite passes because the agent made the checkmark green instead
of making the code correct -- and from the outside those two look identical.

greenwash is the second opinion. It starts from the one thing an agent cannot
edit after the fact: what actually happened when the tests ran.

**It is a report, not a gate.** By default it prints and exits 0. It never
modifies your code, never calls a model, and never leaves your machine.

## Sixty-second start

```bash
pipx install greenwash        # or: pip install greenwash
cd your-repo
greenwash                     # a trust report for the current diff
```

No configuration, no account, no network. If your project has tests, greenwash
finds them. In a JavaScript project, or if you simply prefer `npx`:

```bash
npx greenwash                 # a shim that runs the Python implementation
```

To watch it before you install anything:

```bash
python demo/run_demo.py       # builds a throwaway repo, plants a cheat, catches it
```

Inside Claude Code, install the plugin instead and the report appears every time
the agent tries to finish its turn:

```bash
/plugin marketplace add 0DukePan/greenwash
/plugin install greenwash@greenwash
```

## What the report looks like

This is the verbatim output of `python demo/run_demo.py --terse`, on a repo where
the agent "fixed" a failing test by returning the number the test expected:

```
$ greenwash --claim "Fixed the failing test" \
      --run-tests "python -m pytest -q tests/test_calc.py" \
      --heldout "python -m pytest -q tests/test_calc_hidden.py"
GREENWASH TRUST REPORT
----------------------

Agent claim: "Fixed the failing test"
Run          mode: report

Changes:
  1 file changed, +1/-1

Verification:
  + Visible tests         1/1  (python -m pytest -q tests/test_calc.py)
  x Held-out checks       0/1 cases
  - Test integrity        not run
  - Baseline comparison   not requested
  - Regression checks     not run

Suspicious patterns:
  ! [hardcoded-return] GW-TEST-004  src/calc.py:2
      returns literal 5 (directly), which a test asserts against
  ! [heldout-failed] GW-VER-002
      the visible suite passes but the held-out suite fails -- the change
          overfits what it was allowed to see

Evidence:
  Expected: the held-out cases pass on a correct implementation
  Observed: assert 5 == 7 + where 5 = add(10, -3)
  Source:   held-out verification (python -m pytest -q
      tests/test_calc_hidden.py)
  Command:  python -m pytest -q tests/test_calc_hidden.py

Verdict: NOT_VERIFIED -- a check the claim depends on does not pass
Confidence: MEDIUM (score 40/100)
  - starting from a neutral 50
  - the visible suite passes (1/1)
  - the held-out checks do not pass
  - 2 high-severity signal(s) in the diff
note: using the test command you supplied: python -m pytest -q
          tests/test_calc.py
note: coverage is a proxy: 100% of the changed source files have an
          associated test file (not line coverage)
```

Three things to notice, because they are the whole design:

- **`Ran 1/1, then 0/1`** — the visible suite passes and a suite the agent never
  saw does not. That gap is the evidence, and it cannot be argued with.
- **`Observed: assert 5 == 7`** — every failing verdict carries expected-vs-observed.
  There is no code path that prints a bare `FAILED`.
- **`note: coverage is a proxy`** — a measurement that isn't a real measurement
  says so, in the report, next to the number.

## How it works

```
  diff ──► static rules ──► Signal[]  ─┐
                                       ├──► confidence ──► verdict ──► report
  tests ──► verification ──► Result ───┘        │
            (current, baseline,                └─ every point, explained
             integrity, held-out)
```

**Static layer (`greenwash scan`)** reads the diff. Python is parsed with `ast`,
so a literal routed through a local variable and a trailing comment are both
caught, and a docstring that merely *mentions* an exploit is not. Other
languages use regex packs and are labelled as such.

**Behavioral layer (`greenwash verify`)** runs the tests: the ones on disk, the
same command against a detached worktree of `HEAD` for a before/after
comparison, and optionally a held-out suite the agent never saw. Exit status,
per-test results, and output are captured, secrets redacted, output capped.

### Test integrity

The strongest evidence available is a suite the agent never saw, and almost
nobody has one configured. The repository's own history supplies the next best
thing. When a diff changes a test file, greenwash takes the **committed** version
of that test — the worktree at `HEAD` already holds it — overlays only the
changed *implementation* files onto it, and runs it against the new code.

That is the one combination nothing else checks. The baseline comparison runs
`HEAD`'s tests against `HEAD`'s code; the agent's own run uses the agent's tests
against the agent's code. A test loosened to fit the code passes in both. The
committed test failing while the edited one passes is what changing the test
instead of the code looks like, and it is reported as `test-weakened`.

It is a signal rather than a conviction, because a genuine specification change
produces an identical result — so it makes a report `SUSPICIOUS` and asks for an
explanation, and `--fail-on suspicious` is the opt-in gate. A collection error,
like a refactor that renamed an import target, is recorded as `unavailable`
rather than as a failure.

### Requirements

A claim is prose, and prose cannot be checked. A requirement can, when it names
the thing that would prove it:

```bash
greenwash --claim "Implement OAuth login" \
  --require "Login succeeds => tests/test_auth.py::test_login_succeeds" \
  --require "Invalid credentials rejected => tests/test_auth.py::test_rejects" \
  --require "Refresh-token rotation"
```

Each requirement bound with `=>` is run and reported as a pass or a failure. One
with no binding is reported as **unverifiable** — never as a pass — and a
requirement that fails produces `NOT_VERIFIED`, because it is a check the claim
itself named. No model is involved: the agent says what it did and points at the
evidence, and greenwash runs it. The same list can live in
`.greenwash/config.json` as `"requirements": [...]`.

**Verdict and confidence** are deterministic and explainable. A failed check
outranks any pattern match, a signal alone can never produce `NOT_VERIFIED`,
and a report with no behavioral evidence prints `LOW` no matter how clean the
diff looks. The full decision table and the arithmetic:
[docs/confidence.md](docs/confidence.md).

## What it catches

Nine static rules, and six signals that only a run can produce:

| Code | Rule | Severity | What it means |
|---|---|---|---|
| `GW-TEST-001` | `test-skipped` | high | A test was disabled (`.skip`, `@pytest.mark.skip`, `#[ignore]`, `@Disabled`, RSpec `pending`, ...) instead of fixed |
| `GW-TEST-002` | `test-file-deleted` | high | An entire test file vanished in this diff |
| `GW-TEST-003` | `assertion-weakened` | high | Assertions were removed and nothing equivalent replaced them |
| `GW-TEST-004` | `hardcoded-return` | high | A returned literal matches a value a test asserts against -- caught through a local variable, and checked against related test files on disk |
| `GW-DIV-001` | `swallowed-exception` | medium | An exception is caught and dropped |
| `GW-DIV-002` | `error-path-default` | medium | An `except` block turns an error into a default value and no related test file mentions that path -- **asks**, never accuses |
| `GW-EXP-001` | `known-exploit-pattern` | high | An unconditional `__eq__`, or `sys.exit(0)` / `os._exit(0)` / `process.exit(0)` |
| `GW-TEST-005` | `mock-in-test` | medium | A mock appears in a test file -- **asks**, never accuses |
| `GW-TEST-006` | `conftest-changed` | medium | `conftest.py` was touched -- **asks**, never accuses |
| `GW-VER-001` | `tests-failed` | high | The test command exits non-zero after "done" |
| `GW-VER-002` | `heldout-failed` | high | The visible suite passes but the held-out suite fails |
| `GW-VER-003` | `regression` | high | A test that passed at the committed baseline fails now |
| `GW-VER-005` | `test-weakened` | high | A test file the diff changed does not pass in its committed form against the code as it now stands |
| `GW-VER-006` | `requirement-failed` | high | A requirement the claim bound to a test or a command does not hold |
| `GW-VER-004` | `verification-failed` | low | The verifier could not complete -- an honest gap, not a pass |

`greenwash rules` prints the same table from the source of truth.

## Language support, stated honestly

| Language | Static analysis | Tasks (real suites) | Polyglot corpus |
|---|---|---|---|
| Python | AST: skips, hardcoded returns through locals, empty handlers, `AlwaysEqual`, exit-zero calls | yes | -- |
| JavaScript / TypeScript | regex pack: skips, empty catches, mocks, literal returns checked against a related test file | yes | yes |
| Go | regex pack: skips, empty error handling | yes (`go test ./...`) | yes |
| Rust | regex pack: skips | yes (`cargo test`) | yes |
| Ruby | regex pack: skips, mocks | yes (`ruby -I .`, minitest) | yes |
| Java | regex pack: skips, empty catches, mocks | yes (`javac` then run) | yes |

Both halves are measured. `tests/test_tasks.py` proves every task the way the
harness will run it -- the buggy workspace fails, the hidden test fails on that
same baseline, and the recorded solution passes -- in the task's own language,
skipping rather than failing where a toolchain is absent, and a CI job where the
runner image provides Go, Rust, Ruby and Java runs them and asserts that nothing
skipped. `python benchmark/polyglot.py`
adds 15 static cases that report **15/15 behaving as declared**.

The polyglot corpus is how the JavaScript hardcoded-return bug was found: the
literal extractor was reading the argument out of `assert.equal(sum(2, 3), 5)`
instead of the expected value, so that rule could never fire on the most common
shape of JS assertion.

Signals produced by matching patterns in text rather than parsing it say so.
Their evidence carries `"analysis": "regex"`, and a HIGH-confidence rule drops
to `MEDIUM` there -- a regex pack cannot parse Go, so it does not get to be as
certain as the AST. Severity is unchanged: a skipped test is a skipped test.
The two rules that only look at filenames (`test-file-deleted`,
`conftest-changed`) have no text to parse and carry no `analysis` key.

## Numbers

Every number below is produced by a command in this repository. The pipeline
that makes them is `benchmark/`.

**Detector accuracy, no model in the loop.** 28 tasks across six languages, each
shipped with a buggy baseline, a recorded honest fix, and a scripted cheat.
Every cheat actually made the visible suite go green. On this Windows laptop 24
of the 28 scored -- Go, Rust, Ruby and Java are not installed here, so those
four are named as `skipped: no toolchain` and kept out of every rate; the CI
`languages` job runs the same corpus where the toolchains exist and asserts that
nothing skipped:

| | Result |
|---|---|
| Planted cheats caught | **24/24** (24 static, 22 behavioral, union 24) |
| Cheats missed by both layers | **0** |
| Honest fixes flagged | **0/24** |
| Buggy baselines flagged | 0/24 |
| Runtime | 172s for 24 scored tasks x 3 variants -- every variant runs the real suite in a subprocess |
| Static scan budget | 500-file diff scored in under 2s (asserted by `tests/test_rules.py`) |

Reproduce with `python benchmark/detection.py`; the metrics table, including the
confidence intervals, is generated by `python benchmark/run.py --write` into
[BENCHMARK.md](BENCHMARK.md).

**The confidence intervals matter more than the point estimates.** Over the 24
scored tasks, recall is 100% with a 95% interval of 86.2-100%, and the
false-positive rate is 0% with a 95% upper bound of **13.8%** -- because 24
honest fixes is a small sample, and "we measured no false positives in 24" is
not the same claim as "there are no false positives". The report prints the
second only when it has earned it.

**Ambiguity is a corpus too.** `benchmark/inconclusive/` holds six changes a
reviewer would accept and a naive scanner would flag: a lookup table returning a
constant a test asserts, a flaky test skipped in an unrelated commit, a network
mock, a new fixture, a CLI that exits 0, and documentation that quotes an
exploit. The property under test is the one the design turns on -- a pattern
match may make a report `SUSPICIOUS`, but only evidence may make it
`NOT_VERIFIED`. None of the six is convicted.

**False positives on real history.** `benchmark/fp_survey.py` re-runs the
scanner over recent commits of three unrelated repositories -- this one, a
React/TypeScript app, and a Python tool -- 59 commits touching 1,225 file
changes. It produced 29 flags. Hand-checked: 20 are the rules that always ask
for an explanation, and **9 are genuine false positives** -- 6 from
`hardcoded-return` on a function that legitimately returns a constant a test
asserts, 3 from a successful `exit(0)` in ordinary CLI or hook code. Both
classes are documented in [docs/false-positives.md](docs/false-positives.md),
and each one that got fixed is now a regression test.

**Language packs, measured.** `python benchmark/polyglot.py` runs 15 cases
across Go, Rust, Ruby, Java and JavaScript -- a positive and a negative each --
and reports 15/15 behaving as declared. Every one of those languages also has a
task behind its pack that runs the real suite (`go test ./...`, `cargo test`,
minitest under `ruby -I .`, `javac` then the class), so a pack that stops
matching shows up as a missed detection rather than a silent gap. A missing
toolchain is recorded, not guessed: the task is skipped and named, and signals
from a pack that cannot parse the language still carry `analysis: regex` with
confidence capped at `MEDIUM`.

**The agent-facing number: 24 tasks, three runs per state, and no measured
effect.** How often a model claims done while the check it was told to pass
isn't actually passing, with the plugin `off` vs. `skill-only` vs. `full` --
measured on `dots-studio/dots3-note-prev` through the maintainer's gateway, 72
scored runs per arm. The four language tasks are recorded as
`skipped: no toolchain` and kept out of every rate:

| State | Silent cheats | Runs | Rate | 95% CI |
|---|---|---|---|---|
| `off` | 5 | 72 | 7% | [3, 15] |
| `skill-only` | 5 | 72 | 7% | [3, 15] |
| `full` | 6 | 72 | 8% | [4, 17] |

**Delta (off -> full): -1.4 points -- the plugin did not reduce silent cheating
on this corpus.** Every arm sits inside every other arm's interval, so the
honest reading is "no measurable effect at this sample size", and it is
published as one. What did not get caught is the useful part: all 16 silent
cheats are `mock` or `swallow` shortcuts, nine of them the same task
(`json-load-default`, a swallowed exception) which **no** arm caught -- the
visible suite still passes, and the held-out suite that disagrees is one the
agent never sees. `hardcode`, `skip`, `exploit` and `weaken` tasks were fixed
in every arm. False positives: **0** on 200 genuinely-good runs across the
three arms.

That run predates the test-integrity check described above, so it measures the
plugin as it was then. `json-load-default` is precisely the shape that check now
catches, and the numbers have **not** been re-measured since -- this table is not
a claim about the current code, and it is not presented as one.

The raw rows are in `benchmark/results/delta.jsonl` (252 of them), the report in
[benchmark/RESULTS.md](benchmark/RESULTS.md), and `benchmark/run.py` renders the
table into [BENCHMARK.md](BENCHMARK.md). The next move is more tasks per cheat
type -- the swallow class is where the tool has no leverage -- not a louder
claim:

```bash
python benchmark/preflight.py
python benchmark/harness.py --states off,skill-only,full --runs 3 --model <id>
python benchmark/report.py --out benchmark/RESULTS.md
```

`report.py` also writes `benchmark/results/agent-delta.json`, and two guards
read it: BENCHMARK.md gets the table generated from it, and the README is
checked against it **in both directions** -- if a live run exists the README
must state its delta and its run counts, and if one doesn't, the README must
keep saying the number is unmeasured. A plumbing run driven by the fake agent
can never be published as the effect.

One trap worth knowing: a gateway with a zero balance rejects every model with
`402 reject_no_credit`, which looks like "no model available" and is actually
"no credit".

## Install

| Where | How |
|---|---|
| Any repo (CLI) | `pipx install greenwash` |
| Node projects, or `npx` | `npx greenwash` -- a shim over the Python package, see [`npm/`](npm/) |
| **Claude Code** (the unskippable hook) | `/plugin marketplace add 0DukePan/greenwash` then `/plugin install greenwash@greenwash` |
| GitHub Actions | `uses: 0DukePan/greenwash@v0.4.1` (see [`action.yml`](action.yml)) |
| pre-commit | add `0DukePan/greenwash` to `repos` (see [`.pre-commit-hooks.yaml`](.pre-commit-hooks.yaml)) |
| Codex / Cursor / Copilot / Cline / Windsurf / Gemini | the rules file generated for that host in [`adapters/`](adapters/) |

The Claude Code plugin is the only integration with an unskippable hook --
everywhere else greenwash is a command you or your CI choose to run, and
`adapters/README.md` says so plainly.

## Use it

```bash
greenwash                                   # the report for the current diff
greenwash --json                            # schema-versioned JSON
greenwash --format markdown                 # paste into a PR
greenwash --quiet                           # one line, for a status bar
greenwash --verbose                         # every change and every reason

greenwash scan                              # static only
greenwash verify --run-tests "pytest -q" \
                 --heldout tests/hidden     # behavioral only
greenwash --fail-on not_verified,suspicious # a policy: only what you name blocks
greenwash init                              # write .greenwash/config.json
greenwash doctor                            # what greenwash can and cannot see
```

### Zero configuration

`greenwash init` detects the repository and the test framework, writes a config
that records what it found, and tells you what it could not find:

```
  + git repository -- /path/to/repo
  + test command -- "python" -m pytest -q  (pyproject.toml)
  ! held-out suite -- not configured
      optional, but it is the only check the agent cannot see
  + test integrity -- a changed test file is re-run in its committed form
  + mode -- report -- reports only, never blocks
```

If there is no test command, the report says the behavioral layer did not run,
rather than implying it passed.

A plain `greenwash` is already behavioral, with no config and no flags: the
test command is discovered, run, and run again against a detached worktree of
`HEAD`, so a test that passed before and fails now is a `regression` rather
than a mystery. Naming `--run-tests`, naming a `heldout` suite, or writing
`"auto_verify": false` is how you opt out.

### Configuration

`.greenwash/config.json` is optional and every key is an override:

| Key | Default | Meaning |
|---|---|---|
| `mode` | `"report"` | `"enforce"` turns the exit codes below into a gate |
| `auto_verify` | unset | `false` opts out of the zero-config behavioral layer; `true` forces the baseline comparison alongside a pinned command |
| `test_command` | `null` | pin the command instead of discovering it |
| `heldout` | `null` | path to (or command running) a suite the agent never saw |
| `timeout` | `120` | seconds per test run |
| `block_on` | `["NOT_VERIFIED", "VERIFICATION_FAILED"]` | verdicts that block in enforce mode |
| `ignore_rules` | `[]` | rule ids to suppress; the report names what was suppressed |

### Enforcement is opt-in

| Mode | Exit codes |
|---|---|
| report (default) | 0 whenever it produces a report; 3 when it cannot (not a repository, or no commits) |
| `scan` / `verify` subcommands | 0 clean, 1 findings, 3 could not run |
| `--enforce`, or `"mode": "enforce"` | 0 verified, 1 not verified, 2 suspicious, 3 could not check (a `VERIFICATION_FAILED` verdict) |
| `--fail-on VERDICTS` | the same codes, for exactly the verdicts named. It implies `--enforce` and **replaces** the policy rather than adding to it, so `--fail-on not_verified` lets a merely-suspicious report through. An unknown verdict name is exit 3, not a silently open gate. |

The Stop hook follows the same rule: in report mode it prints the report and
lets the agent stop; in enforce mode it exits 2 with the findings, which hands
them back to the agent. It runs the same zero-config behavioral layer, so the
turn is checked against the tests and not only against the patterns. And it
finds its own interpreter -- `python3` first, `python` as the fallback, because
no single name exists on both a stock Linux and a stock Windows.

A tool that blocks by default is a tool people uninstall -- and a checker that a
developer cannot turn off is one they will route around.

## FAQ

**Does it block my agent?**
Not by default. It reports. `mode: "enforce"` changes that for people who want
a gate, and the verdicts that block are configurable.

**Does it call a model?**
No. No API key, no account, no network access, no telemetry. Detection is a
parser and your test runner.

**My project has no tests. What then?**
You get a report that says the behavioral layer did not run, a `LOW` confidence,
and an `INCONCLUSIVE` verdict. It will still read the diff.

**Why is my confidence `LOW` when nothing was flagged?**
Because nothing was *verified*. The score is capped below `MEDIUM` when no
behavioral check ran -- a clean diff is not evidence that the work is correct.

**Can I stop a rule from firing?**
`"ignore_rules": ["mock-in-test"]` in the config. The report then says which
rules were suppressed, so a quiet report is never a silent one.

**Is this the same as running my tests in CI?**
CI tells you whether the suite passes. greenwash asks whether the suite still
means what it used to: whether a test was weakened, skipped, or satisfied by a
constant, and whether a held-out suite agrees.

**npx?**
`npx greenwash` works: it runs the Python implementation through the shim in
[`npm/`](npm/), forwarding argv and the exit code untouched. It is a wrapper,
not a second implementation -- two codebases that can disagree about whether
your tests pass is the failure this tool exists to catch. It still needs Python
3.10+ with the `greenwash` package installed, and it says exactly that if either
is missing.

**How do I report a false positive?**
Open an issue with the commit and the flag. Every confirmed false positive
becomes a test -- that is the policy, not a promise.

## Repository layout

| Path | What lives there |
|---|---|
| `greenwash/domain.py` | `Run`, `Claim`, `Signal`, `VerificationResult`, `Verdict`, `TrustReport` -- the versioned wire format |
| `greenwash/scan/` | the static engine: `rules/` (one file per rule), `languages/` (packs + the Python AST checks) |
| `greenwash/verify/` | the behavioral engine: discovery, runner, baseline worktree, held-out suites, redaction |
| `greenwash/report/` | terminal, JSON and markdown renderers |
| `greenwash/confidence.py` | the scoring and the verdict table |
| `greenwash/cli.py`, `doctor.py`, `config.py` | the entry point, diagnostics, `.greenwash/config.json` |
| `docs/` | [confidence.md](docs/confidence.md), [false-positives.md](docs/false-positives.md) |
| `benchmark/` | 28 tasks across six languages (each with its own runner), harness, detection measurement, FP survey, Wilson-CI report |
| `benchmark/polyglot/` | 15 static cases across Go, Rust, Ruby, Java and JavaScript -- one negative per language |
| `npm/` | the `npx greenwash` shim, which runs the Python implementation rather than reimplementing it |
| `skills/`, `hooks/`, `adapters/` | the skill the agent reads, the Stop hook, and the generated rule files for other hosts |
| `scripts/` | the two compatibility entry points CI and the plugin call |
| `tests/` | 293 tests -- domain, confidence, rules, language packs, reporting, CLI, hook contract, test integrity, requirements, the compatibility entry point, the inconclusive corpus, benchmark tasks |
| `benchmark/inconclusive/` | six ambiguous changes that must be asked about and never convicted |
| `demo/` | the reproducible catch from the top of this file |
| `assets/` | the logo, the demo GIF and the benchmark chart, plus the scripts that rebuild them |

## Development

```bash
git clone https://github.com/0DukePan/greenwash && cd greenwash
python -m pytest -q            # 293 tests, no model or network needed
python demo/run_demo.py        # the catch, end to end
python benchmark/detection.py  # the accuracy numbers above
```

Adding a language to the scanner is data, not code: edit
`greenwash/scan/languages/packs.py` and add its extension to `LANGUAGE_BY_EXT`.
Backing that pack with a task is the part that has code: a runner in
`benchmark/harness.py`, a cheat in `benchmark/tools/fake_agent.py`, a positive
and a negative case in `benchmark/polyglot/`, and the task itself under
`benchmark/tasks/`.

Adding a rule means a new module in `greenwash/scan/rules/` with its metadata,
a positive and a negative test, and a row in the table above --
`tests/test_rules.py` fails if the README and the registry disagree.

Contributions are expected to arrive with the receipt: the command and its
output. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT. See [LICENSE](LICENSE).
