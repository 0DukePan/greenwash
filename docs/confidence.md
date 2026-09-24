# Confidence and verdicts

Two decisions come out of every report: a **verdict** and a **confidence**. Both
are deterministic — the same inputs always produce the same answer — and both
are explainable, because the report prints the sentences that produced them.

## The verdict

The verdict is a decision table, applied in order. The first line that matches
wins.

| # | Condition | Verdict |
|---|---|---|
| 1 | The verifier itself could not complete | `VERIFICATION_FAILED` |
| 2 | The visible test command exits non-zero | `NOT_VERIFIED` |
| 3 | The visible suite passes and the held-out suite fails | `NOT_VERIFIED` |
| 4 | A test that passed at the baseline fails now | `NOT_VERIFIED` |
| 5 | A requirement the claim bound evidence to does not hold | `NOT_VERIFIED` |
| 6 | A high-severity signal that is not `requires_review`, or a changed test that fails in its committed form | `SUSPICIOUS` |
| 7 | Nothing ran, and no signals | `INCONCLUSIVE` |
| 8 | Signals, but nothing contradicts the claim | `PARTIALLY_VERIFIED` |
| 9 | A requirement nobody could check | `PARTIALLY_VERIFIED` |
| 10 | The visible suite passes | `VERIFIED` |
| 11 | Anything else | `INCONCLUSIVE` |

Two properties are deliberate:

- **Evidence outranks inference.** A failed check beats any pattern match. A
  signal on its own can never produce `NOT_VERIFIED` — the tool does not get to
  convict anyone on a regex. A *requirement* is different: the claim named it
  and bound evidence to it, so failing it is a check the claim depends on, and
  rule 5 puts it with the other failed checks.
- **An honest gap is not a pass.** If nothing ran, the verdict is
  `INCONCLUSIVE`, never `VERIFIED`. `VERIFICATION_FAILED` is distinct from
  `INCONCLUSIVE`: the first means we tried and broke, the second means there was
  nothing to try. A requirement with no evidence bound is the same kind of gap,
  and rule 9 keeps it out of `VERIFIED`.

`test-weakened` (GW-VER-005) sits at rule 6 rather than rule 4 on purpose. The
committed version of a changed test failing against the new code is real
evidence, but a legitimate specification change produces an identical signal —
so it asks for an explanation instead of convicting. `--fail-on suspicious` is
the opt-in gate for teams that want it to block.

## The score

```
base                          50
visible suite passes         +20
held-out checks pass         +15
baseline comparison passes   +10
each high-severity signal    -15
each medium-severity signal   -5
each failed requirement      -15
coverage below 0.5           -10
```

Clamped to `[0, 100]`, then mapped to a level: **LOW** below 40, **MEDIUM**
40–70, **HIGH** above 70.

Three things worth knowing:

- **A perfect run scores 95, not 100.** The base is 50 and the three bonuses
  add 45. The missing five points are the honest part: no automated check
  proves a change is correct, only that the checks that ran did not object.
- **`requires_review` signals are not counted.** `mock-in-test` fires on any new
  mock, including entirely correct ones. Scoring it would punish good work, so
  it asks for a human look and costs nothing.
- **Nothing ran caps the score at 39.** Neutral is not the same as confident: a
  report with no behavioral evidence prints `LOW` whatever the diff looks like.

There is no floating point anywhere in this path, and no percentage is ever
printed. `63.27%` implies a calibration nobody has measured.

## `requires_review`

| Rule | Why it only asks |
|---|---|
| `mock-in-test` | Mocking is normal, correct practice. The question is whether the mock replaced the unit under test, which a regex cannot answer. |
| `conftest-changed` | Fixture and hook edits are routine; conftest can *also* mask failures repo-wide, which is why it is worth a look either way. |
| `error-path-default` | `except KeyError: return None` is idiomatic and frequently correct. The rule only fires when nothing nearby tests that path, which makes it worth a look rather than a mark against the work. |

## Coverage

`coverage` is a **proxy**, and the report says so in its notes: the share of
changed source files that have an associated test file. It is not line
coverage. Line coverage would need a coverage plugin the project may not have,
and reporting `0%` for a project without one would be a lie dressed as a number.
It is only used for the `< 0.5` deduction, and it is `null` when it cannot be
computed.

## Reproducing a score

Every report carries the terms:

```
Confidence: MEDIUM (score 65/100)
  - starting from a neutral 50
  - the visible suite passes (84/84)
  - the held-out checks do not pass
  - no suspicious patterns detected
```

Add the numbers in those sentences and you get the score. If that ever stops
being true, it is a bug — `tests/test_confidence.py` asserts each term.
