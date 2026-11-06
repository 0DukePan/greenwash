# Contributing to greenwash

Thanks for helping. Two things make this project worth having: the checks
stay honest, and the benchmark numbers stay reproducible.

## Run the tests

Three commands, in the order you will use them:

```bash
python -m pytest -q                 # 10 seconds: pure units and the claim guards
python -m pytest -q -m "not program"  # the product's real gate, about seven minutes
python -m pytest -q -o addopts=     # everything, including the frozen programme
```

The default is deliberately not everything. A test that spawns a process -- a
CLI, a hook, a git repository, a benchmark harness -- carries the `slow`
marker; the frozen research programme carries `program`. CI runs the default on
both supported Pythons, the product gate on every push, and everything on a
nightly schedule (including Windows). If you change shipped behaviour, run the
product gate before you push.

Add a test with every new check or language pack. Disabling, weakening or
deleting a test to make the suite green is the failure this project exists to
catch -- fix the code or explain, in the pull request, why the test was wrong.

## How work is tracked

GitHub Issues, one issue per change. There are no ticket files in the tree and
no separate tracker: the issue is the spec, the pull request links it, and a
closed issue with a merged pull request is the record. If an issue needs more
than a paragraph, put the detail in the pull request description rather than in
a new document.


## Add a language pack

Language support is data, not code. Edit `greenwash/scan/languages/packs.py`:

1. Add the file extensions to `LANGUAGE_BY_EXT`, e.g. `".kt": "kotlin"`.
2. Add a matching key to `PACKS` with three lists:
   - `skip` -- how this language disables a test (`@Ignore`, `t.Skip(`, ...)
   - `swallow` -- how it drops an error silently (empty `catch`/`except`)
   - `mock` -- how it mocks a dependency in a test file
3. Add a positive **and a negative** case to the table in `tests/test_rules.py`.

Python additionally gets structural checks in `greenwash/scan/languages/python_ast.py`.
Other languages are regex-only for now; a real parser for a second language
is welcome.

After changing anything under `greenwash/` or `skills/`, run
`python benchmark/tools/sync_skill_only.py`. The skill-only benchmark state
ships its own copy of the checker, and `tests/test_manifests.py` fails if the
two drift -- otherwise the benchmark would compare two detectors instead of
one detector with and without the hook.

## Add a rule

One module in `greenwash/scan/rules/`, exporting a `RULE` (id, code, title,
category, severity, confidence, description, remediation) and a `check(ctx)`
that returns `Signal[]`. Then:

- a positive and a negative fixture in `tests/test_rules.py`,
- a row in the README's table -- `tests/test_rules.py` fails if the registry and
  the README disagree about which rules exist,
- `requires_review=True` if the rule asks a question rather than raising an
  accusation. Those never move the confidence score and never decide a verdict.

Rules the behavioral layer raises live in `greenwash/verify/signals.py` and use
the same `Rule` shape.

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
