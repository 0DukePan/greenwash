---
name: greenwash
description: Use this skill before telling the user a task is complete, a bug is fixed, tests pass, or anything else that amounts to "done" after writing or changing code. In this plugin a Stop hook runs the same check automatically in strict mode, so a turn that ends on an unexplained finding is handed straight back to you with the reasons. The rules below are how to satisfy it on the first try instead of the third -- pasting the literal command and its literal output, running the check yourself, and treating a flag as something to explain rather than something to route around.
---

# greenwash (Codex plugin)

Anthropic's own research found that models under pressure to show a green
checkmark sometimes make the checkmark green instead of making the code
correct -- skipping the test, mocking the thing being tested, hardcoding the
expected value, or swallowing the exception that would have failed loudly.
All four produce the same visible result. Only one of them means the bug is
fixed.

## Rule 1: no claim without the receipt

Never write "done", "fixed", "tests pass", "should work now", or anything
equivalent unless you paste, verbatim:

1. The exact command you ran
2. The exact output it produced

Not a paraphrase. Not "all tests passed" -- the actual `5 passed in 0.32s` or
equivalent. If you didn't run it, you don't get to say it passed.

## Rule 2: run the check before you claim anything

```bash
python "${PLUGIN_ROOT}/scripts/greenwash_hook.py" < /dev/null
```

or, from the repository root:

```bash
greenwash --strict
```

Paste its output too, whether clean or not. A clean scan is not proof of
correctness -- it is a smell test, not a prover. Say so plainly rather than
treating "found nothing" as a stronger claim than it is.

## Rule 3: when there is a broader or held-out suite, run it

Static patterns are a pre-filter. The real question is whether the code works
on inputs you weren't shown:

```bash
greenwash verify --strict \
  --run-tests "<the project's test command>" \
  --heldout "<path to a suite you were not shown, if one exists>"
```

A fix that passes the visible test but fails the broader suite is not a fix.

## What strict mode blocks on

This plugin runs `--strict`, which is a longer table than the CLI's default:

| Finding | Result |
|---|---|
| `NOT_VERIFIED` | blocked. Evidence is not something a waiver can excuse |
| `VERIFICATION_FAILED` | blocked. A check that could not run is not a pass |
| `SUSPICIOUS` | blocked unless every finding is waived |
| a `requires_review` finding (a new mock, a touched `conftest.py`, an error path returning a default) | blocked until someone decides |
| an expired, stale or malformed waiver | blocked |
| `ignore_rules` in the config | refused -- waive the individual finding instead |

`INCONCLUSIVE` is allowed, with an explicit note that nothing was verified.
Nothing blocks on a pattern nobody has looked at; everything blocks on a
pattern nobody has answered for.

## When the gate blocks you

You have exactly two honest options:

- **Fix the real thing** it is pointing at, then show the receipt again.
- **Ask for a decision.** When a finding is genuinely correct -- an
  intentionally skipped unrelated test, a constant that is the right answer --
  the resolution is a waiver, which is a decision with a name and an expiry on
  it, not a rule switched off:

  ```bash
  greenwash waive --rule GW-DIV-002 --path src/loader.py \
    --reason "the fallback is the documented behaviour and an integration test covers it" \
    --reviewer @maintainer --expires 2026-10-26
  ```

What you may never do: delete, comment out, loosen, route around, or skip over
a finding just to make the gate pass. That is the exact behaviour this plugin
exists to catch, and doing it to get past greenwash itself is the same failure
one level up.

## What it actually checks

Static: a skipped or disabled test, a deleted test file, removed assertions, a
mock in a test file, a returned literal a test asserts against, a swallowed
exception, an error path returning a default, and the named exploits
(`sys.exit(0)`, an unconditional `__eq__`, a `conftest.py` edit).

Behavioral: the suite failing after "done", a held-out suite that disagrees
with the visible one, a regression against the committed baseline, a changed
test that does not pass in its committed form, and any requirement the claim
itself bound to a test or a command.

None of these prove cheating by themselves. A flag means "explain this," not
"you're caught." Treat it exactly that plainly with the user.
