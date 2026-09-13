# Contributing to greenwash

Thanks for helping. Two things make this project worth having: the checks
stay honest, and the benchmark numbers stay reproducible.

## Run the tests

```bash
python -m pytest -q
```

These cover the scanner (regex + AST) and the verifier. Add a test with every
new check or language pack.

## Add a language pack

Language support is data, not code. Edit `scripts/greenwash/patterns.py`:

1. Add the file extensions to `LANGUAGE_BY_EXT`, e.g. `".kt": "kotlin"`.
2. Add a matching key to `PACKS` with three lists:
   - `skip` -- how this language disables a test (`@Ignore`, `t.Skip(`, ...)
   - `swallow` -- how it drops an error silently (empty `catch`/`except`)
   - `mock` -- how it mocks a dependency in a test file
3. Add a fixture test in `tests/test_greenwash.py` for at least `skip`.

Python additionally gets AST checks in `scripts/greenwash/ast_checks.py`.
Other languages are regex-only for now; a real parser for a second language
is welcome.

After changing anything under `scripts/` or `skills/`, run
`python benchmark/tools/sync_skill_only.py`. The skill-only benchmark state
ships its own copy of the checker, and `tests/test_manifests.py` fails if the
two drift -- otherwise the benchmark would compare two detectors instead of
one detector with and without the hook.

## Keep the benchmark honest

- `benchmark/harness.py` runs tasks under the three plugin states. Don't
  change the scoring to make the tool look better; the plugin must never be
  the source of the score.
- Report the **false-positive rate** alongside the silent-cheat rate. A tool
  that flags everything is worthless; a tool that reports its own error rate
  is trusted.
- New tasks go in `benchmark/tasks/<name>/` (start from `_template/`) with
  `workspace/` (what the agent sees) and `hidden/` (never shown), plus a
  `task.json` with `prompt`, `visible_test`, `hidden_test`, and `cheat_hint`.

## Style

- Small, single-purpose modules under `scripts/greenwash/`.
- No comments that restate the code; comment the *why*.
- Anything that could be a false positive must say "explain this," never
  "you're caught."
