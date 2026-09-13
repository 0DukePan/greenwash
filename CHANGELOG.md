# Changelog

## Unreleased

### The v1 surface: a trust report instead of a flag list

- **A package you can install.** `greenwash/` is a real package with
  `pyproject.toml` and a console script, so `pipx install greenwash` works.
  `scripts/greenwash_check.py` stays as the compatibility entry point that the
  Action, the pre-commit hook, CI, the benchmark harness and the demo all call,
  with its command line, stdout and exit codes unchanged.
- **A domain model with a versioned wire format** (`greenwash/domain.py`):
  `Run`, `Claim`, `FileChange`, `Evidence`, `Signal`, `VerificationResult`,
  `Verdict`, `Confidence`, `TrustReport`. `schema_version: "1"`. Serialization
  never raises: unknown keys are ignored, wrong types degrade to defaults, and
  a malformed report becomes an empty one rather than a traceback.
- **A verdict** (`VERIFIED`, `PARTIALLY_VERIFIED`, `SUSPICIOUS`,
  `NOT_VERIFIED`, `VERIFICATION_FAILED`, `INCONCLUSIVE`) from a documented
  decision table, and **a deterministic confidence score** whose every point is
  a sentence in the report. No percentages -- see `docs/confidence.md`.
- **Signals carry their own metadata**: rule id, stable code (`GW-TEST-004`),
  title, category, severity, confidence, files, line, evidence, remediation,
  and `requires_review` for the two rules that ask rather than accuse.
- **Three report formats** (terminal, JSON, markdown) from one `TrustReport`,
  with `--quiet` and `--verbose`. Every failing verdict carries
  expected-vs-observed evidence; there is no path that prints a bare `FAILED`.
- **Zero-config activation**: `greenwash init` detects the repo and the test
  command, writes `.greenwash/config.json`, and says what it could not find;
  `greenwash doctor` diagnoses the same things. The report is the default
  action: `greenwash` with no arguments.
- **Enforcement is opt-in** (`--enforce` or `"mode": "enforce"`) with stable
  exit codes 0/1/2/3. Report mode always exits 0 -- the report is the product.
- **The Stop hook reports by default** and only blocks the agent's turn in
  enforce mode. 0.3 always blocked; that was the wrong default for a tool whose
  value is being believed.

### Verification

- Evidence on every failure: expected, observed, source, command, case id.
- Secret redaction on all captured output, output capped per stream, a timeout
  on every run, and `harness_error` to distinguish "we could not check" from
  "the check failed".
- `coverage` is computed and **named as the proxy it is** (share of changed
  source files with an associated test file), and the note saying so travels
  with the number in the report.

### Bugs found while building this

- **The package claimed `requires-python = ">=3.10"` while three lines needed
  3.12.** Two multi-line f-strings had a nested quote inside the expression and
  a third had a `\u` escape there, which is only legal from 3.12 (PEP 701). The
  guard test compiles every directory with a real 3.10 interpreter; the obvious
  `ast.parse(feature_version=(3, 10))` check does **not** catch it -- the grammar
  is fine, the tokenizer objects -- and reported "0 files needing more than 3.10"
  while CI was red.

- **`git add -N -A` without a pathspec** indexed the entire enclosing
  repository. In a subdirectory of a monorepo -- or in a temp directory sitting
  under a `git init`-ed home directory, which is exactly what happened here --
  that is minutes of work and an index belonging to someone else. Now scoped
  with `-- .`, with regression tests for both the scope and the related-test
  lookup (diff paths are repository-root relative).
- **The exploit rule ran the regex table over Python**, which contains those
  very patterns as string literals, so the scanner flagged its own pattern
  table and its own docstrings. Python is AST-only now; a test pins it.
- **`endswith(".py")` misread a command as a file path**, turning
  `python -m pytest -q tests/x.py` into `pytest -q "python -m pytest ..."` --
  which fails with "file or directory not found" and looks like a real
  held-out failure.
- **The CLI forced ANSI colour on when piped**, so `greenwash > report.txt` and
  every CI log filled up with escapes. Colour is now decided from the stream,
  with `--color` to force it.
- **A report with no behavioral evidence claimed MEDIUM confidence**, because
  the neutral base of 50 maps to MEDIUM. Confidence is now capped below MEDIUM
  when nothing ran: neutral is not confident.
- **`git diff HEAD` in a repository with no commits** surfaced git's three
  different wordings ("bad revision", "ambiguous argument", "does not have any
  commits yet") as a raw error. It is checked up front and reported as one
  clear sentence.
- **`assertion-weakened` is count-based**, so a real assertion replaced by a
  useless one has an unchanged count and is not flagged. Documented in
  `docs/false-positives.md` rather than left as a surprise.

### Tests

- 59 -> 161. New: domain round-trips and malformed-input tolerance, every
  confidence term and every verdict branch, positive **and** negative cases for
  every rule, the 500-file/2s scan budget, all three report formats, the CLI's
  exit codes in both modes, the hook's report-vs-enforce contract, and the
  inconclusive corpus.
- `tests/test_readme.py` holds the README to its own numbers: the test count
  against collection, the headline against `detection.json`, the
  false-positive split against `fp-survey.json`.

### Benchmark

- `benchmark/run.py` publishes the metrics -- true/false positives and
  negatives, recall, precision, false-positive rate, per-cheat-type breakdown --
  with 95% Wilson intervals, and writes them into `BENCHMARK.md` between
  markers. It reads artifacts and refuses to invent absent measurements: an
  unmeasured figure is printed as unmeasured, with the command that would
  produce it.
- The intervals are the honest part: recall is 100% (95% CI 86.2-100%) and the
  false-positive rate is 0% with a **13.8% upper bound**, because 24 honest
  fixes is a small sample.
- `benchmark/inconclusive/` adds six ambiguous changes -- a lookup table, a
  skipped flaky test, a network mock, a new fixture, a CLI that exits 0, and
  documentation quoting an exploit -- each with a case file saying why it is
  ambiguous and which rules may fire. The test asserts that none of them is
  convicted: a signal may produce `SUSPICIOUS`, only evidence may produce
  `NOT_VERIFIED`.
- `scan_diff(..., root=...)` lets a caller whose diff paths are not
  repository-root relative say so, which is what the synthetic corpus needs.

### Docs

- `docs/confidence.md` (the arithmetic and the verdict table) and
  `docs/false-positives.md` (measured classes, known limitations, how to
  suppress a rule).
- README rewritten around the report.

### Demo

- `demo/run_demo.py` now drives the real CLI and prints a trust report; the GIF
  is generated from it, and since the report is taller than the window the
  generator scrolls the viewport the way a terminal does and settles on the
  verdict. `--terse` is what the GIF shows.


- Upgraded `assets/demo.gif` again: a two-line kicker above the terminal
  (`An agent "fixed" the failing test.` / `It hardcoded the answer.`), so the
  clip explains itself without its caption, and each flag tag brightens for
  140ms as it lands so the catch registers while it is happening. 768x482,
  6.5s loop, 748 KB. The kicker is the only non-verbatim element and the
  caption says so.
- Trimmed the GIF's palette to 96 colours plus forced accents; the pulse
  colour costs a few KB and the frame count went up, and this pays it back.

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
