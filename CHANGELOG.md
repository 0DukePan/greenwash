# Changelog

## Unreleased

- Rewrote the README around real captured output (the demo's two layers and a
  live `Stop`-hook block), with badges, a numbers section that states what is
  and isn't measured, an install matrix, a usage section, a repository map, and
  an FAQ.
- New visuals: `assets/logo.svg` is a brushed, still-wet checkmark (with
  `assets/logo-mark.png` as its rasterized form), and `assets/demo.gif` is a
  7.6s loop of the demo -- the claim, the flag, the blocked stop -- rebuilt by
  `assets/make_demo_gif.py` with Pillow.
- Fixed the documented test gate: `python -m pytest -q` no longer collects the
  benchmark task fixtures from the repo root (`pytest.ini` pins
  `testpaths = tests`). It used to fail with 21 collection errors and leave
  `__pycache__` inside the task workspaces.
- Task validation and the benchmark harness exclude `__pycache__`/`*.pyc` when
  copying a workspace, so stale bytecode compiled from the buggy baseline can
  no longer shadow the solution overlay.
- `task.json` `hidden_test` paths are generated with forward slashes, so the
  benchmark suite runs on Linux/macOS as well as Windows.
- The skill-only control plugin is resynced with the main checker (it had
  drifted) and a test now enforces the two staying identical;
  `benchmark/tools/sync_skill_only.py` does the copying.
- `benchmark/tools/fake_agent.py` works for every task (not just
  `src/calc.py`) via `GREENWASH_BENCH_TASK_DIR`, and benchmark rows carry an
  `agent` field; `benchmark/report.py` banners any run that was not a live
  model.
- Added `benchmark/tasks/_template/`; task directories whose name starts with
  `_` are skipped by the harness and the structural tests.
- `verify --auto` test discovery prefers a declared `package.json` test script
  over a bare `tests/` directory.
- Stop hook timeout raised 60s -> 180s: `verify --auto` runs the suite twice
  (current tree + committed baseline).
- Added `tests/test_hook.py`: the Stop hook's exit-0/exit-2 contract is tested
  against the documented JSON payload, so the enforcement layer stays covered
  even when no model is reachable.
- CI's no-model harness step now asserts the planted hardcode is still
  classified as a silent cheat, instead of only checking that the harness ran.
- `action.yml`: quoted a description containing `(default: HEAD)` -- the
  unquoted colon made the file invalid YAML, which GitHub rejects.

## 0.3.0

- Renamed the project to **greenwash**.
- Split the checker into a package (`scripts/greenwash/`) with a real CLI:
  `scan`, `verify`, `all`.
- **Zero-config behavioral verification**: `verify --auto` discovers the test
  command, runs the suite on the current tree and on a detached worktree of
  `HEAD`, and flags tests that passed at baseline and fail now (`regression`).
- **Python AST checks** (`ast_checks.py`): hardcoded returns are now caught even
  when routed through a local variable (`result = 5; return result`) or
  annotated with a trailing comment (`return 5  # fixed`) — both slipped past
  the old regex.
- **Data-driven language packs** (`patterns.py`) for Python, JS/TS, Go, Rust,
  Ruby, and Java.
- **Benchmark**: harness records `cheat_type`; `report.py` reports the
  silent-cheat delta with a Wilson 95% CI, a false-positive rate, and a
  per-cheat-type breakdown; `preflight.py` fails fast when no model is
  reachable.
- Added: `LICENSE` (MIT), CI (Linux + Windows, Python 3.10/3.12),
  `.pre-commit-hooks.yaml`, `action.yml`, `adapters/`, `demo/run_demo.py`,
  `THREAT_MODEL.md`, `CONTRIBUTING.md`, `.claude-plugin/marketplace.json`.
- Stop hook now honours `GREENWASH_AUTO`, `GREENWASH_TEST_CMD`,
  `GREENWASH_HELDOUT`.

## 0.2.0

- Restructured into a valid Claude Code plugin (`.claude-plugin/plugin.json`,
  `hooks/hooks.json`, `skills/greenwash/SKILL.md`, `scripts/`).
- Fixed `hardcoded-return` missing a literal followed by a trailing comment.
- Documented the `result = 5; return result` limitation (since closed in 0.3.0).

## 0.1.0

- Initial Stop hook + skill: flags skipped tests, mocked units-under-test,
  hardcoded returns, swallowed exceptions, `sys.exit(0)`, `conftest.py`
  changes, and unconditional `__eq__` overrides.
