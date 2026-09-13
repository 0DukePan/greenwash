# Changelog

## Unreleased

- Rebuilt `assets/demo.gif` again, this time for density: `run_demo.py` grew a
  `--terse` mode (commands and output only), so the GIF carries 13 lines
  instead of 21 at roughly a third larger type in a 768x420 frame, with each
  flag block tinted behind an amber tag and an amber edge down its left side.
  6.2s loop, 687 KB, frame accuracy re-verified after paletting.
- The GIF's palette is now built from the art's own colours with the accents
  forced in: Pillow's adaptive quantisation was silently dropping the green
  `$` -- 52 green pixels in, 0 out.
- `benchmark/fp_survey.py` measures the scanner against real history -- 59
  commits touching 1,225 file changes across three repositories -- and writes
  `benchmark/results/fp-survey.json`: 29 flags, 20 of them the
  ask-for-an-explanation rules and 9 genuine false positives. Both classes are
  now listed in `THREAT_MODEL.md`.
- Two false-positive classes the survey found are fixed: docs and configs
  (`.md`, `.json`, `.yml`) are no longer scanned as code, and Python skip
  detection is AST-based, so a file that merely *mentions* `@pytest.mark.skip`
  -- the scanner's own pattern table -- is no longer flagged. Both have
  regression tests.
- The detection measurement attacks each task with the cheat it was designed
  to tempt (`FAKE_AGENT_CHEAT=auto` instead of one generic hardcode) and breaks
  the result down by cheat type: static scan 24/24, held-out suite 22/24,
  false positives 0/24. The two behavioral misses are the exploit pair --
  `__eq__` returning True, a patched `conftest.py` -- because both tricks
  satisfy the hidden test too; only the static layer catches them.
- Task validation got stricter: the hidden test must now fail on the buggy
  baseline by itself, not just as part of a failing suite. That caught three
  hidden tests that passed on their own bug (`unique-preserve-order`,
  `is-palindrome-stub`, `safe-divide`); all three were strengthened.
- Host instruction files (`AGENTS.md`, Cursor, Copilot, Cline, Windsurf,
  Gemini) are generated from the skill by `adapters/sync_instructions.py`, so
  the rules cannot drift between hosts; a test fails when they do. Only the
  Claude Code plugin additionally gets the unskippable Stop hook.
- Restyled `assets/demo.gif` after a frame-by-frame review. The poster frame is
  now the caught state rather than an empty terminal, the flag tags are
  highlighted so the catch reads at thumbnail size, the dead beats at the loop
  point are gone (6.1s loop), and the frames are actually downsampled from the
  2x render -- the GIF had been shipping at 1440x1120 and 1.9 MB; it is now
  720x550 and 1.0 MB.
- `benchmark/detection.py` measures the checker against the corpus with no
  model: 18/18 planted cheats caught (13 of them by the static scan alone),
  0 false positives on the 24 recorded real fixes. `assets/benchmark.svg`
  charts it, and the README's numbers section now leads with measured figures
  instead of a pending paragraph.
- Fixed the harness littering the temp directory on Windows: `remove_tree`
  retries past git/pytest handle lag (481 orphaned run directories had piled
  up before this).
- The benchmark covers JavaScript as well as Python: three `node --test` tasks
  (`js-sum-offbyone`, `js-parity-inverted`, `js-json-count`), 24 in total. The
  harness and the structural tests dispatch on the task's `language`, and the
  scripted agent cheats in JS too.
- Fixed two detector gaps the JS tasks exposed: `assert.equal/strictEqual(x, v)`
  literals were never collected, so a hardcoded JS return went unflagged; and
  `tests/<name>.test.mjs` was not guessed as a related test file.
- Rewrote the README around real captured output (the demo's two layers and a
  live `Stop`-hook block), with badges, a numbers section that states what is
  and isn't measured, an install matrix, a usage section, a repository map, and
  an FAQ.
- New visuals: `assets/logo.svg` is a brushed, still-wet checkmark, and
  `assets/demo.gif` types out the demo's real stdout -- captured by running it,
  not transcribed -- on a clean terminal card, built by
  `assets/make_demo_gif.py` with Pillow.
- `demo/run_demo.py` wraps its output to a terminal width, so the long flag
  detail lines no longer run past 120 columns.
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
