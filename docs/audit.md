# Phase 1 audit

Read-only audit for the no-regret hardening phase. Branch `phase1-hardening`, cut from `spec/launch-benchmark` at `85e01dd` plus the spec and questionnaire commit. `main` was not touched and this branch is local.

## Baseline

Command run on the branch tip, whole suite, no flags:

```
python -m pytest -q
```

Result, verbatim from the run: `724 passed, 7 skipped in 740.13s (0:12:20)`. Zero failures, zero errors. The skip count matches the four language tasks without a toolchain plus the documented conditional skips; the README's test-count pin reads 731 and matches the collected total.

## Architecture

- **CLI surface.** `greenwash/cli.py` builds the parser and dispatches `scan`, `init`, `doctor`, `rules`, `waive`, `evidence`, and the verification entry points. Exit codes are `0` ok, `1` findings, `2` suspicious, `3` could not check, `4` integrity refusal.
- **Static layer.** `greenwash/scan/` owns the rule registry, the language packs, and the AST module. Rules cover test integrity (skips, deletion, weakened assertions, hardcoded returns, mocks, conftest, verifier config), divergence, exploit patterns and verifier configuration.
- **Verdict engine.** `greenwash/domain.py` defines the `Verdict` and `Outcome` enums and the report model. `greenwash/confidence.py` owns the decision table (`verdict_for`), the evidence precedence (TAMPERED over INCONCLUSIVE over WEAK_VERIFIER over CLEAN), the mechanism plus grade-relevance rule, and the scoring.
- **Verification layer.** `greenwash/verify/` runs the test command (`runner`, `results`), the baseline comparison, the held-out suite, test integrity, requirement binding, the pinned-evidence resolver (`pinned.py`), and the strength advisory (`strength.py`). The engine composes them in `engine.py`.
- **Evidence and enforcement.** `greenwash/guard.py` hash-checks the checker, config and pinned tests; `greenwash/waivers.py` owns waivers; `greenwash/hooking.py` and `scripts/` plus `codex/` implement the fail-closed stop hooks; `greenwash/evidence.py` validates corpora and preregistrations.
- **Benchmark tooling.** `benchmark/` owns the seeded task corpus (`detection.py`), the tampering study with twins (`tampering.py`), the evaluation runner and interval math (`evaluation.py`), the launch criteria engine (`criteria_engine.py`), pre-registration and the burn ledger (`preregistration.py`), the launch command (`launch.py`), the reproduction command (`reproduce.py`), the behavioral protocol runner (`protocol.py`), the claim ledger (`claim_ledger.py`), and the frozen impossible corpus.
- **Launch command.** `benchmark/launch.py` is the single seam: it enforces refusals, assembles the computed table and the L1 to L9 inputs, calls the criteria engine, writes the report and the decision record, and exposes `status_line` for the README. The criteria and thresholds data live in `benchmark/thresholds.json`, loaded through `benchmark/preregistration.py`.
- **Docs.** `docs/specs/` holds the evidence-verdicts spec, revision 2 of the launch benchmark, and the validation program. `docs/what-did-not-work.md`, `docs/RESULT_INTERPRETATION.md`, `docs/benchmark-summary.md`, `benchmark/RESULTS.md` and `BENCHMARK.md` carry the measured or provisional numbers. `THREAT_MODEL.md`, `SECURITY.md` and `docs/EVALUATION_PROTOCOL.md` carry the trust and method statements.

## Docs-versus-repo gaps (verified)

1. **The master prompt named by this phase's brief (`greenwash-plan.md`) does not exist in the repository.** The brief itself was treated as self-contained.
2. **`ROADMAP_TO_TRENDING.md` still uses the retired v1 taxonomy and numbers** ("silent cheat", the off-versus-full comparison). It was not updated by the 2026-10 correction and contradicts `docs/what-did-not-work.md`.
3. **The README's headline detector numbers are not labeled as maintainer-authored or preliminary.** The 24-of-24 and 0-of-24 figures are from the maintainer's own task corpus, and the launch-benchmark spec says those are plumbing, not evidence.
4. **The claim ledger has no source-type or limitation fields.** It records claim, evidence, status and allowed wording, but not whether evidence is a unit test, maintainer-authored, independent, frozen or beta, and not the limitation sentence per claim.
5. **Launch thresholds exist twice with no consistency test.** `benchmark/thresholds.json` and the table in `docs/specs/launch-benchmark.md` agree today by inspection, but nothing fails when one moves.
6. **The criteria engine's unevaluable state is a free-text reason (`not evaluated`), not a first-class UNMEASURED state.** The launch status line has `UNMEASURED`, but a criterion-level state does not. A LAUNCH is impossible today because unevaluable criteria fail, but the vocabulary is not shared.
7. **Fail-safe behavior is untested per case for several infra inputs.** Timeout is handled (runner sets `timed_out`, engine raises a harness error, verdict is VERIFICATION_FAILED), and a harness error outranks everything. Empty diff, parse failure, missing dependency, missing original tests and a signed-out infra failure have no one-test-per-case guarantee that they cannot yield a passing verdict.
8. **`THREAT_MODEL.md` exists at the repository root, but the brief's `docs/threat-model.md` does not.**
9. **`action.yml` exists but no workflow uses the report-only mode**, and the twin-pair demo exists only as a benchmark script, not as a labeled artifact a reader can read.
10. **`benchmark/results/headline.md` is a fixture-corpus rebuild whose sample-floor gate fails by design.** It is linked from the README Methods section, which is accurate about reproducibility and should say plainly that it is a plumbing fixture, not the frozen evaluation.
11. **The README test-count pin is manual.** Every added test requires a manual repin, and a stale pin is a red suite.

No claim is made here that any file or number is wrong beyond what is stated; each item above was read in the repository during this audit.
