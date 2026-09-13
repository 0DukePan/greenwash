# False positives

A checker that flags everything is worthless, so the false-positive story is
published next to the catch rate rather than buried. This page lists every
class of false positive that has been **measured**, not guessed.

## Measured on real history

`benchmark/fp_survey.py` re-runs the scanner over recent commits of three
unrelated repositories — this one, a React/TypeScript app, and a Python tool —
59 commits touching 1,225 file changes. It produced **29 flags**:

| Class | Count | What to do |
|---|---|---|
| Rules that always ask for an explanation (`mock-in-test`, `swallowed-exception`, `test-skipped`, `assertion-weakened`, `conftest-changed`) | 20 | Look, decide, move on. These are questions, not accusations. |
| `hardcoded-return` on a function that legitimately returns a constant a test asserts | 6 | Ask whether the function has any reason to return that value. A month name or a `'0.00'` default usually does. |
| `known-exploit-pattern` for `exit(0)` in ordinary CLI or hook code | 3 | It matters when the tests import that file. An exit at the end of `main()` is normal. |

Full list, flag by flag: [`benchmark/results/fp-survey.json`](../benchmark/results/fp-survey.json).
The classes above are the ones a user is most likely to meet.

## Known limitations, stated plainly

| Rule | Limitation |
|---|---|
| `hardcoded-return` | A constant a test asserts against is textually identical to a cheat. This is why the rule reports `SUSPICIOUS` and never `NOT_VERIFIED` on its own. |
| `assertion-weakened` | Counts assertions, so it cannot tell `assert True` from `assert total == 42`. A test edited from one real assertion to one useless assertion has an unchanged count and is not flagged. `verify` is what catches that, by running the suite. |
| `known-exploit-pattern` | `sys.exit(0)` at the end of a CLI is idiomatic. Python is parsed, so docstrings and pattern tables that merely *mention* an exploit are not flagged — that was a real bug once, and `tests/test_rules.py` pins it. |
| `mock-in-test`, `conftest-changed` | Fire on correct code. Both are `requires_review`, so they never move the score and never decide a verdict. |
| Language packs | Python has structural (AST) checks. JavaScript/TypeScript, Go, Rust, Ruby and Java are regex-only, so they are noisier and are not backed by tasks in the benchmark. |

## Reducing noise

`.greenwash/config.json` accepts `ignore_rules`:

```json
{ "ignore_rules": ["mock-in-test"] }
```

Suppressed rules are named in the report's notes, so a reader always knows what
was left out rather than seeing a suspiciously quiet report.

## The rule this project holds itself to

Every confirmed false positive becomes a test. The two most recent:

- The scanner used to match its **own pattern table** — a Python file holding
  `"sys.exit(0)"` as a string literal was flagged as an exploit.
- Docs and configuration files used to be scanned as code, so a README
  explaining an exploit was flagged.

Both are now regression tests. If you find a false positive, the useful bug
report contains the commit and the flag; it becomes a fixture, not a promise.
