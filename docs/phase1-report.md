# Phase 1 report: no-regret hardening

Branch `phase1-hardening`, cut from `spec/launch-benchmark` and never touching `main`. Eight commits plus one log-hygiene commit. Diff against the branch point: 21 files, 954 insertions, 254 deletions (the spec and questionnaire commit that predates Phase 1 is excluded).

The phase brief named `greenwash-plan.md`; that file does not exist in the repository, so the brief itself was treated as the specification. The `/implement-spec` worktree machinery was not used because the brief prescribed its own branch-and-commit procedure.

## Commands run, with their real results

| Command | Result |
|---|---|
| `python -m pytest -q` at the branch tip, before any change | `724 passed, 7 skipped in 740.13s`, zero failures |
| `python -m pytest tests/test_failsafe.py` after the fail-safe fix | `7 passed` (six infra cases plus the control) |
| `python -m pytest tests/test_failsafe.py tests/test_confidence.py tests/test_inconclusive.py tests/test_strict.py tests/test_nothing_ran.py tests/test_cli.py -q` | `141 passed` |
| `python -m pytest tests/test_decision_criteria.py -q` | `8 passed` |
| `python -m pytest tests/test_criteria_engine.py tests/test_launch_command.py -q` | `105 passed` after the UNMEASURED change (the only failure was the README count pin, then repinned) |
| `python -c ... clopper_pearson(11, 11)` and `(0, 11)` | `0.7150858470818455` and `0.28491415291815436`; Wilson 0.7412 and 0.2588 |
| `python benchmark/claim_ledger.py --matrix` | generated `docs/claim-matrix.md`; 35 docs-gate tests pass |
| `python .scratch/phase1/demo_twin.py` | tamper: exit 1, `assertion-weakened`; twin: exit 0, clean |
| scan overhead, medians of three runs | itsdangerous 352.3/401.2 ms, cachecontrol 726.6/397.1 ms, this repo 426.9/405.5 ms (clean/changed) |
| `python -m pytest -q` at the final tip | `741 passed, 7 skipped in 1491.00s`, zero failures |
| `python scripts/greenwash_check.py scan` | `clean -- nothing here fakes a passing suite` |

## Step-by-step

0. **Audit.** `docs/audit.md`: architecture, verdict engine and launch command locations, the baseline above, and eleven verified docs-versus-code gaps, including the missing master prompt and the stale `ROADMAP_TO_TRENDING.md` numbers.
1. **Fail-safe verdicts.** One test per infra case (`tests/test_failsafe.py`). Found and fixed one real hole: a passing suite whose committed form could not be re-run returned `VERIFIED`; an unavailable integrity check now yields `INCONCLUSIVE`. Timeout, missing dependency and internal failure already mapped to `VERIFICATION_FAILED`; parse failure and empty diff to `INCONCLUSIVE`.
2. **Decision criteria.** Criteria rows now carry `MEASURED` or `UNMEASURED`; the decision lists `unmeasured_criteria` and cannot return LAUNCH while any exists. Eight tests pin the L1/L2 boundaries, empty dataset, malformed report, conflicting cells, the sample floor, and that `benchmark/thresholds.json` matches the launch spec's L-table.
3. **Statistics.** Recomputation above. The classes are now stated explicitly in the evaluation module: positives, twins, natural clean, weak verifier; planted and synthetic records never enter a rate.
4. **Claims.** Every ledger row carries a source type from a fixed vocabulary and a limitation sentence; `docs/claim-matrix.md` is generated and drift-tested. README headline says "planted tampers", marks the figures maintainer-authored and preliminary, states the exact intervals, and defines the verdicts and the limits pointer.
5. **Report-only beta.** `.github/workflows/greenwash-report-only.yml` (pull_request, read-only, artifact, never fails), `docs/beta.md` with install and exit codes, and `demo/twin-pair/` with captured real output. Overhead measured and published.
6. **Security.** `docs/threat-model.md` with assets, adversaries, surfaces and six larger open issues. Fixed the one clear issue: the composite action interpolated workflow inputs into its shell script; inputs now arrive as environment variables passed as argv.

## Unfinished work

- No real corpus, no independent labels, no frozen split. The launch status is `UNMEASURED` and the README says so.
- The README headline is still a maintainer-authored number; it is labeled preliminary, not replaced.
- Replay-mode runtime was not measured; only the static scan was.
- `action.yml` and the workflows reference actions by tag, not by full commit SHA (needs network verification).
- No sandbox enforcement for replay on untrusted code; documented, not built.
- The base branch (`spec/launch-benchmark`) remains unmerged, and this branch sits on top of it.

## Needs human input

- Independent labeler and adjudicator for Stage 1.
- 5 to 10 consenting repositories for Stage 5 shadow/report-only trials.
- 5 to 8 developers for the usability test.
- Licensing decisions for R3 and R4 corpora.
- The judge choice and the frozen prompt (B2).
- Confirmation whether the v4 "Ratchet" is the pinned competitor (B3).
- The pre-registered launch configuration.
- The advisor's answers to `to-questionnaire-greenwash-launch-worthiness.md`, which decide the recommendation below.

## Draft recommendation: halve Stage 1 and 2, run Stage 3 on dev, defer Stage 4, start Stage 5 report-only now

- **Stage 1: halved.** Build the dev corpus at the spec's minimum, 60 per class, and calibrate labeling time on 20 cases before committing to the double-labeled 100. The measurement machinery exists; the cost is human hours, and the current 71.5/28.5 bounds cannot move without real cases.
- **Stage 2: halved and sequenced.** After the first dev measurement, build matched evidence/no-evidence pairs for HC1, HC4 and HC11 at 12 dev cases each, and let the observed failures choose the rest. Do not pre-build all twelve families.
- **Stage 3: full on dev.** The competitor is pinned and the adapters exist; this is cheap and it is the decisive input to Gate A. Run the judge only if Gate A is close on H1 and H3.
- **Stage 4: deferred.** Do not build the frozen split until Gate A says the detector is worth it. The launch command, burn ledger and criteria engine are ready; the corpus is the gate.
- **Stage 5: report-only now.** It is built, the static overhead is sub-second, and it licenses only the wording already allowed. Nothing beyond report-only until Gate B and Gate C.

This recommendation is pending the questionnaire answers and is not a decision.
