# Report mode versus strict mode

Same checker, same diff, same evidence. The difference is what happens to the
turn when the evidence lands.

## The three profiles

| | report (default) | `--enforce` | `--strict` |
|---|---|---|---|
| What it is for | reading | a policy you name | an agent that finishes its own turn |
| `VERIFIED` | report | allow | allow |
| `INCONCLUSIVE` | report | allow | allow, with a "nothing was verified" note |
| `PARTIALLY_VERIFIED`, no review findings | report | allow | allow |
| `NOT_VERIFIED` | report | block (1) | block (1) -- evidence is not waivable |
| `VERIFICATION_FAILED` | report | block (3) | block (3) |
| `SUSPICIOUS` | report | block (2) | block (2) unless every finding is waived |
| a `requires_review` finding | report | allow | block (2) until it is waived |
| expired / stale / malformed waiver | report | allow | block (2, or 3 when unreadable) |
| `ignore_rules` | honoured, and named | honoured, and named | **refused** (3), findings stay visible |
| Exit code when it cannot run | 3 | 3 | 3 |

`--enforce` and `--strict` return the same codes for the same verdicts. Strict
adds three rows, and the third of them is the reason it exists.

## Run side by side

Both blocks below are captured output from the two demo scripts in this
repository, on the same throwaway repo: a test asserting `add(2, 3) == 5` and an
implementation that returns the literal `5`.

**Report mode** -- `greenwash scan` on that diff:

```
$ greenwash scan --quiet
⚠ greenwash: suspicious (low confidence) -- 1 signal(s)
exit code: 1
```

Findings reported, nothing blocked. (The `scan` subcommand exits 1 on findings
in every mode; a bare `greenwash` in report mode exits 0 and prints the whole
report.)

**Strict mode** -- the Claude hook, on the same diff, at the end of a turn:

```
greenwash: SUSPICIOUS (medium confidence)
  strict gate: blocked -- the diff contains a pattern that needs an explanation: [hardcoded-return] src/calc.py:2
  visible tests: 1/1

Suspicious patterns to explain:
  [hardcoded-return] src/calc.py returns literal 5 (directly), which a test asserts against
exit code: 2
```

Note what did *not* change: the finding, the evidence, the verdict. What changed
is that the turn does not end until someone answers for it.

Reproduce both with `python demo/strict_claude.py --terse` and
`python demo/strict_codex.py --terse`.

## What strict mode costs

It is not free, and the cost is reviews.

- **A `requires_review` finding blocks until it is decided.** `mock-in-test`
  fires on *any* new mock, including honest ones; `conftest-changed` fires on
  any `conftest.py` edit. In report mode those are questions. In strict mode
  they are a stopped turn until a human (or the agent, with a named reviewer
  recorded) decides.
- **The escape hatch is a waiver, not a config key.** `greenwash waive` writes
  one decision to `.greenwash/waivers.json`: one rule, one path, one
  fingerprint, a reason, a reviewer, and an expiry no more than 30 days out.
  It is more work than adding a rule to an ignore list. That is the point --
  and the reason strict mode refuses to run past `ignore_rules` rather than
  quietly honouring it.
- **Evidence cannot be waived at all.** If the held-out suite failed, strict
  mode blocks and no signature changes that. A waiver is a decision about a
  *pattern*; it is not a decision about what happened.

## Which one to pick

| Situation | Profile |
|---|---|
| You want to read a report before merging by hand | report (the default, no flags) |
| CI should fail on a faked pass, and you decide what blocks | `--fail-on not_verified` (or `--enforce`) |
| A pre-commit hook, the GitHub Action | `--enforce` / the Action's default |
| An agent ends its own turn and you want an answer for every finding | `--strict`, or the Claude / Codex plugin |
| A repo with no held-out suite and a lot of honest mocks | report mode plus a review habit -- strict will cost you reviews it cannot earn back |

The last row is a real trade-off, not a hedge. Strict mode is the profile for a
repository that has decided the review cost is worth it, which is why it is opt-in
everywhere and why the CLI default is the one that never blocks.
