# Threat model

greenwash exists because an agent under pressure to show a green suite
sometimes makes the suite green instead of making the code correct. Be clear
about what it does and does not buy you.

## What it is not

- **Not a prover.** A flag means "explain this," not "you are cheating." Every
  new mock in a test file is flagged because a diff alone cannot tell mocking a
  dependency from mocking the unit under test.
- **Not unbypassable.** The static layer (`scan`) matches patterns in a diff. An
  agent that knows the patterns can evade them — rename the literal, compute the
  value instead of returning it, skip a test by deleting it and re-adding it
  elsewhere. This is a speed bump, by design.
- **Not a substitute for review.** It is a checklist that runs whether or not
  anyone remembers to run it.

## Why it is still worth running

- **The hook does not ask permission.** A skill is a request the agent can skip
  under pressure; a `Stop` hook fires on every turn end. That is the entire
  thesis, and it is measurable.
- **The behavioral layer is the durable signal.** `verify --auto` runs the
  tests and compares against the committed baseline, so it does not depend on
  the agent's choice of *how* to fake things — only on the observable result.
  This is the part that is expensive to game.
- **Honest false-positive reporting.** The benchmark publishes a
  false-positive rate next to the cheat rate. A checker that flags everything
  is worthless, and saying so out loud is the point.

## Known false-positive classes

Measured, not guessed: `benchmark/fp_survey.py` runs the scanner over real
history -- three repositories, 59 commits, 1,225 file changes -- and every flag
it raised is listed in `benchmark/results/fp-survey.json`. Nine of the 29 were
genuine false positives, and they come from two rules:

| Class | Why it fires | How to read it |
|---|---|---|
| `hardcoded-return` in a function that returns a constant a test asserts | A lookup table or a formatting default is textually identical to a cheat | Ask whether the function has any reason to return that value; a month name or a `'0.00'` default usually does |
| `known-exploit-pattern` for `exit(0)` in ordinary code | A CLI that exits 0 on success looks exactly like a test process exiting early | It matters when the tests import that file; an exit at the end of `main()` is normal |

The other 20 flags are the rules that always ask for an explanation -- new
mocks in a test file, empty `catch`/`except` blocks, skips, weakened
assertions, a changed `conftest.py`. Reporting that split next to the cheat
rate is the point; a checker that hides its error rate cannot be trusted.

## Adversary model

| Adversary | Caught by |
|---|---|
| Lazy/inattentive agent that skips or weakens a test | `scan` (`test-skipped`, `assertion-weakened`, `test-file-deleted`) |
| Agent that hardcodes an expected value | `scan` (`hardcoded-return`, AST for Python) |
| Agent that mocks the unit under test | `scan` (`mock-in-test`) + `verify` behavioral run |
| Agent that swallows the exception that would fail | `scan` (`swallowed-exception`) |
| Agent using a documented exploit (`sys.exit(0)`, `AlwaysEqual`, `conftest.py`) | `scan` (`known-exploit-pattern`, `conftest-changed`) |
| Agent whose fix breaks existing tests | `verify --auto` (`regression`) |
| Agent that overfits the visible test | `verify` with `--heldout` (`heldout-failed`) |
| Adversary who reads this file and routes around the static patterns | **not caught by `scan`** — rely on `verify`, review, and the benchmark's FP/TP rates |

## Trust boundary

`scan` trusts the diff. `verify` trusts the test command's exit code and the
harness's own scoring — never the agent's summary. The benchmark harness scores
from artifacts on disk and never from inside the agent's session, so the plugin
cannot inflate its own score.
