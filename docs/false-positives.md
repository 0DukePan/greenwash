# False positives

A checker that flags everything is worthless, so the false-positive story is
published next to the catch rate rather than buried. This page lists every
class of false positive that has been **measured**, not guessed.

## Measured on real history

`benchmark/fp_survey.py` re-runs the scanner over recent commits of ten
unrelated repositories -- Python and JavaScript/TypeScript, 250 commits
touching 1,029 file changes. The first run produced **109 flags**, 104 of them
one asking rule on CI and dependency configuration; that rule was narrowed and
the same history now produces **14 flags**:

| Class | Count | What to do |
|---|---|---|
| `verifier-config-changed` on a real runner change -- a `test` script rewritten, a hook's `exclude` or `args` narrowed, a tox environment given a dependency | 7 | Read it. All seven in the second run were genuine changes to what runs; version bumps no longer produce a flag. |
| `conftest-changed` | 3 | Look, decide, move on. Fixture changes are normal; the flag is a question. |
| `error-path-default` on an error turned into a default that no nearby test mentions | 2 | Both are one `pytest` change seen through a commit and its merge: one is a true ask (the fix landed without a test) and one is a false positive (the merge carried the regression test, but the rule does not look in pytest's `testing/` directory). Read the handler and decide whether the default is right. |
| `assertion-weakened` where a narrowed `pytest.raises(...)` implies the removed type assertion | 1 | Read the removed lines. Two assertions removed and one added can be a stricter test. |
| `swallowed-exception` on a deliberate empty `catch {}` in a test | 1 | Check whether the assertions after the catch are the point; if they are, the catch is not hiding a result. |

Full list, flag by flag: [`benchmark/results/fp-survey.json`](../benchmark/results/fp-survey.json);
both runs are written up in [false-positive-survey.md](./false-positive-survey.md),
and `tests/test_launch_docs.py` fails when this table's counts disagree with the
artifact.

An earlier survey over three repositories (59 commits, 1,225 file changes, 29
flags) found 9 false positives in two classes that are still worth knowing
about, and each fixable one became a regression test:

| Class | Count | What to do |
|---|---|---|
| `hardcoded-return` on a function that legitimately returns a constant a test asserts | 6 | Ask whether the function has any reason to return that value. A month name or a `'0.00'` default usually does. |
| `known-exploit-pattern` for `exit(0)` in ordinary CLI or hook code | 3 | It matters when the tests import that file. An exit at the end of `main()` is normal. |

## Known limitations, stated plainly

| Rule | Limitation |
|---|---|
| `hardcoded-return` | A constant a test asserts against is textually identical to a cheat. This is why the rule reports `SUSPICIOUS` and never `NOT_VERIFIED` on its own. |
| `assertion-weakened` | Counts assertions, so it cannot tell `assert True` from `assert total == 42`. A test edited from one real assertion to one useless assertion has an unchanged count and is not flagged. `verify` is what catches that, by running the suite. |
| `known-exploit-pattern` | `sys.exit(0)` at the end of a CLI is idiomatic. Python is parsed, so docstrings and pattern tables that merely *mention* an exploit are not flagged — that was a real bug once, and `tests/test_rules.py` pins it. |
| `mock-in-test`, `conftest-changed` | Fire on correct code. Both are `requires_review`, so they never move the score and never decide a verdict. |
| `error-path-default` | Measured on the ten-repository survey: two flags on one `pytest` change, one a true ask and one a false positive. It is `requires_review`, and its related-test lookup only guesses a sibling `test_<stem>.py` or a `tests/`, `test/` or `__tests__/` directory, so a project that keeps its tests elsewhere can be flagged after the path is tested. A default is also sometimes the right answer (`except KeyError: return None`), which is why the rule asks rather than accuses. |
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
