# Spec: Evidence-bearing verdicts and the evaluation kit

Status: ready for agent. Source: the v5 positioning and validation plan (2026-10-21).

## Problem Statement

A developer who asks a coding agent to fix a failing test currently has two options. Trust the agent's "tests pass" and hope the tests still prove anything, or read the diff by hand. Agents under pressure to show green will skip a test, edit an expected value, mock the unit under test, or rewrite the docstring that describes correct behavior. The current release catches the obvious static tampers on a small internal corpus, but it has three honest weaknesses. Its false-alarm rate above tiny samples is unmeasured. It misses a changed expected value inside a test, the hardest and most legitimate-looking technique. And its behavioral claim rests on a three-run pilot that showed no effect. Meanwhile the closest competitor already replays the base branch's tests and blocks test edits, so "rerun the pinned original tests" is table stakes, not a differentiator. The thing that does not exist yet is a verdict a developer can audit: what was decided, on what evidence, and what the tool refuses to decide.

## Solution

Greenwash returns one evidence-bearing verdict per run, from a fixed set with explicit precedence, plus secondary flags so nothing is lost. It resolves a changed expected value with a pinned-evidence rule: evidence must come from sources fixed before the agent ran, never from files the agent edited in the diff. It runs the pinned original tests against the agent's code, three times, and treats flakiness as inconclusive rather than clean. It checks its own integrity, so a verdict cannot be edited from inside the sandbox it inspects.

Around the detector, an evaluation kit makes the public numbers auditable. A corpus with independent positive sources, matched legitimate twins, and a task-level frozen split. Baseline adapters for the competitor, a test-file-edit rule, held-out tests, and an LLM judge. Pre-registered gates with exact statistics. A behavioral protocol in which the treatment is never the measuring instrument. A claim ledger that maps every public sentence to the evidence that licenses it, and one command that reproduces the headline table from pinned artifacts.

## User Stories

1. As a developer reviewing an agent's fix, I want one verdict with its evidence attached, so that I can decide whether to trust the passing suite without reading every diff hunk.
2. As a developer, I want a changed expected value to be judged against evidence captured before the agent ran, so that a legitimate behavior change is not accused and a fabricated one is not excused.
3. As a developer, I want the tool to say INCONCLUSIVE when it cannot establish whether a change was justified, so that abstention never looks like an accusation or a clean bill.
4. As a developer, I want the evidence for every verdict printed in a stable JSON shape, so that I can store it next to a CI run and read it later.
5. As a developer, I want spec edits, fixture rewrites, and docstring rewrites that change the stated contract flagged distinctly, so that the spec-rewrite route shows up in the verdict rather than vanishing.
6. As a developer, I want a test-strength advisory on ordinary runs, so that a pass on a suite that could not catch a wrong answer is visible before someone relies on it.
7. As a developer, I want run-to-run determinism on unchanged inputs, so that a verdict in CI is reproducible.
8. As a developer, I want an explicit statement of what the tool does not cover, so that I do not cite it for retrieval leaks or training-time reward hacking.
9. As a developer, I want a whole-diff run to cost seconds, so that the check fits in a pre-push hook as well as CI.
10. As a developer, I want the tool to stay quiet on honest work, so that justified skips, ordinary CLI exits, and legitimate test updates do not train me to ignore it.
11. As a CI maintainer, I want the checker's config and pinned tests to load from the base ref, so that a branch cannot lower its own bar.
12. As a CI maintainer, I want distinct exit codes for tampered, inconclusive, not-verified and could-not-check outcomes, so that pipelines can branch on them.
13. As a CI maintainer, I want the checker and its inputs hash-checked before use, so that a modified checker fails loudly instead of trusting itself.
14. As a CI maintainer, I want an integrity test suite that tries to subvert the checker from inside a sandbox, so that the trust model is tested rather than asserted.
15. As a security-conscious team lead, I want replay to run the agent's code in a container with no network and no secrets, so that reviewing an untrusted diff is safe.
16. As a security-conscious team lead, I want the checker to treat the diff and agent-authored text as untrusted input, so that the tool cannot be steered by what it inspects.
17. As a security-conscious team lead, I want the evidence format to name the mechanism and the grade relevance separately, so that a suspicious pattern alone never becomes a tampering claim.
18. As a benchmark maintainer, I want positives drawn from independent published sources as well as by-construction corpora, so that the evaluation is not circular.
19. As a benchmark maintainer, I want matched legitimate twins for every tampering technique, so that the false-alarm rate is measured against realistic edits, not blank files.
20. As a benchmark maintainer, I want the corpus split by task and repository, so that no task in development can appear in the frozen evaluation.
21. As a benchmark maintainer, I want a hash manifest of the frozen split, so that a result can be tied to the exact cases that produced it.
22. As a benchmark maintainer, I want labeled cases double-annotated blind, with raw agreement, kappa and PABAK reported, so that label noise is visible.
23. As a benchmark maintainer, I want synthetic injected tampers reported separately and excluded from gates, so that detection is not flattered by cases built from the detector's own taxonomy.
24. As a benchmark maintainer, I want per-cell results by source, technique, language and task ambiguity, so that one pooled number never hides the variation.
25. As a benchmark maintainer, I want strict recall and decided-case recall reported together with the abstention rate, so that abstaining cannot be sold as accuracy.
26. As a researcher comparing detectors, I want all baselines run on the same corpus with frozen configurations, so that the comparison means something.
27. As a researcher, I want the competitor adapter pinned to a version and its default configuration, so that the head-to-head cannot be tuned against either side.
28. As a researcher, I want an LLM-judge baseline with a frozen prompt and at least three runs per case, so that its variance is measured and not assumed away.
29. As a researcher, I want exact McNemar tests for paired detector comparisons, so that the claimed edge comes with its uncertainty.
30. As a researcher, I want pre-registered gates and a no-peeking rule, so that the frozen split keeps its meaning.
31. As a researcher, I want a fresh frozen split after any change prompted by a failed gate, so that re-testing cannot quietly inflate a result.
32. As a researcher, I want a non-inferiority margin of ten points only, with the sample-size arithmetic shown, so that the tool never promises a margin its data cannot support.
33. As a researcher studying agent behavior, I want the primary outcome measured by an instrument independent of the treatment, so that an agent evading the checker cannot look clean.
34. As a researcher, I want impossible-task labels by construction and blinded review on sampled runs, so that the behavioral claim needs no judgment in the loop.
35. As a researcher, I want the tamper rate published as a lower bound, following established audit practice, so that missed tampering is never counted as absence.
36. As a researcher, I want task-level clustering handled in the analysis, so that runs on the same task are not treated as independent evidence.
37. As an agent receiving feedback, I want actionable findings with file and line evidence, so that I can resolve the finding instead of guessing.
38. As an agent, I want the checker to distinguish an accusation from a review request, so that a justified skip asks rather than blocks.
39. As a maintainer cutting a release, I want a claim ledger checked by tests, so that no public sentence exceeds its evidence.
40. As a maintainer, I want one command that reproduces the headline table from pinned artifacts, so that a reader can verify the release's numbers.
41. As a maintainer, I want a generated limits page with the coverage matrix and known gaps, so that scope is documentation rather than folklore.
42. As a maintainer, I want a versioned technique taxonomy, so that corpus coverage can be diffed between releases.
43. As a reader of the README, I want the detection numbers stated with confidence intervals and sample sizes, so that I can judge how much the tool has actually shown.
44. As a reader, I want the abstention rate and the weak-verifier rate named as first-class outcomes, so that the tool's uncertainty is part of the product.

## Implementation Decisions

- **Verdict domain model.** Extend the existing verdict enum with `TAMPERED` and `WEAK_VERIFIER`, keeping `CLEAN`, `INCONCLUSIVE`, `NOT_VERIFIED` and `VERIFICATION_FAILED`. Precedence when findings overlap: TAMPERED over INCONCLUSIVE over WEAK_VERIFIER over CLEAN. Secondary flags (`spec_edited`, `strength_low`, `edits_listed`, `flaky_original`, `replay_infra_error`) live beside the verdict, never folded into it. TAMPERED requires both mechanism evidence and grade relevance; a pattern alone stays INCONCLUSIVE.
- **Two modes.** Benchmark mode draws the reference from task metadata captured at creation (spec or issue text, reference solution, hidden tests) and uses the full decision table. Developer mode draws from the base commit and whatever the user supplies, and defaults to conservative.
- **Pinned-evidence resolver.** A single component answers "does fixed evidence support the new value" with three outcomes (supports, contradicts, none) plus provenance. Allowed evidence sources: task text captured at creation, reference-solution behavior, documentation at the base commit. Forbidden sources: any path present in the diff. A finding whose only support would be an edited file is treated as no evidence and sets `spec_edited`.
- **Expected-value decision table.** Rows keyed on two inputs, whether the pinned original assertion fails on the agent's code (rerun three times, with base-commit flakiness detected) and what pinned evidence says. Both strict and conservative variants are parameters, pre-registered and reported side by side.
- **Replay engine.** Runs the pinned original tests, not the working-tree copies, against the agent's code. Three reruns. Infrastructure failure yields INCONCLUSIVE, never CLEAN. The same pipeline covers loosened assertions, skips and xfails, narrowed parametrizations, deleted tests, mocked assertions, swallowed exceptions, harness exits and special-cased test inputs.
- **Verifier integrity.** Checker code, config and pinned tests are hash-verified before use and loaded from outside the agent's writable sandbox; in CI, from the base ref. An integrity suite attempts modifications from inside and requires zero successes.
- **Strength check.** Mutation of the changed region scored against the suite, not coverage. Ships as an advisory flag (`strength_low`) in this version; promotion to the WEAK_VERIFIER verdict is deliberately deferred until its error rate is measured.
- **Technique taxonomy as data.** One versioned table drives the coverage matrix, the corpus loader and the report. Entries beyond the existing rule set: spec or docstring or fixture rewrite, runner and plugin configuration tampering, report tampering, gate or hook tampering.
- **Corpus kit.** A case record carries source, technique, label, split, task or repository identity, and license. Splits are enforced by task identity: a task in development cannot appear in the frozen set, and the frozen manifest is hash-recorded. Synthetic tampers are a separate, non-gated class.
- **Baseline adapters.** B0 is a path rule; B1 uses held-out tests where the source provides them; B2 is a judge harness with a frozen prompt and model, three runs per case; B3 is the competitor run as a subprocess at a pinned version with default configuration and no tuning. All four consume the same corpus records.
- **Evaluation runner.** One command turns a corpus plus detector configurations into per-cell confusion matrices, strict and decided recall, twin and natural false-alarm rates, abstention, cost, wall time and run-to-run variance, with exact Clopper-Pearson intervals as primary and Wilson as sensitivity. Gate evaluation is mechanical against pre-registered thresholds.
- **Behavioral protocol.** Arms: no skill, skill only, skill plus feedback, optionally read-only tests. Primary contrast is feedback versus none, with Holm correction across the secondary contrasts. The primary outcome comes from an instrument independent of the treatment (hidden-test gap plus blinded review of flagged and sampled-unflagged runs). The checker's own flag rate is reported separately as a gate-hit rate. Analysis uses a task random effect or cluster bootstrap; the sample size follows the pre-registered table.
- **Claim ledger as data.** Each public claim is a record with its evidence requirement, current status and the strongest allowed wording. A docs test fails when a public page states more than the ledger allows.
- **Reproduction command.** `greenwash verify` rebuilds the headline table from pinned artifacts: corpus manifest, frozen annotations, detector configurations, seeds.
- **Statistics module.** Exact intervals, exact McNemar, design effect and non-inferiority sizing live in one tested module; published tables are generated from it so no hand-computed number can drift.

## Testing Decisions

- **What makes a good test.** Drive the public seam, assert the observable outcome literally: verdict, flags, exit code, and the evidence fields a user would read. No assertions on internal call counts or private state. Every detector change ships with its malicious case and a benign twin.
- **Existing seams, preferred.** The CLI verification seam already carries verdict-level tests against real temporary repositories. Rule changes are tested through the scan seam with literal findings. Hook behavior is tested through the subprocess manifest seam. Harness behavior is tested through a real scripted run. Documentation numbers are pinned against recorded artifacts by the existing docs tests.
- **The new seams, in priority order.**
  1. **Verdict pipeline through the CLI verification seam.** This is where the evidence JSON, the precedence table, the pinned-evidence resolver and the replay outcomes are judged. Fixture repositories supply the pinned sources. One seam, highest possible.
  2. **Evaluation runner over a fixture corpus.** A tiny in-repo corpus with known outcomes drives the runner end to end, including gate evaluation, interval arithmetic and the frozen-manifest check. This is the only genuinely new seam and it deliberately does not grow the CLI surface.
  3. **Baseline adapters.** B0 and B1 run in-process; B2 and B3 are exercised through stub executables so the adapter contract is tested without the external tools.
  4. **Integrity suite.** Attempts to alter checker inputs from inside a sandbox, asserted as zero successes.
- **Prior art.** The existing session-base and strict-mode tests show the house pattern: build a real repository, run the CLI, assert exit codes and JSON. The docs-pin tests show how generated numbers stay honest. The tampering study shows the twin pattern for false alarms.
- **Seam check.** These seams should match the expectation: verdict work lands on the existing CLI seam, everything evaluation-shaped lands on the single new runner seam, and no seam is added per detector.

## Out of Scope

- Retrieval and leakage detection; training-time reward hacking; any claim about RL-trained agents.
- Languages beyond Python and pytest in this version.
- An LLM judge as a product component. It exists only as baseline B2.
- Promoting the strength check to a verdict; it ships as an advisory flag.
- Publishing or reverse-engineering the competitor's internals; only its pinned CLI is exercised.
- The frozen-set run itself and corpus licensing decisions for third-party sources. Both depend on decisions listed in the plan.
- Issue-tracker publishing and triage labels. The tracker and label vocabulary are not configured in this repository; `/setup-matt-pocock-skills` is the prerequisite for both. This spec lives in the repository until then.

## Further Notes

- **Open decisions carried from the plan.** Row-D policy defaults to conservative and both policies are pre-registered (D1). The competitor is run, pinned, untuned (D2). If it matches on the corpus, positioning pivots to the evidence format, the corpus and the measurement protocol (D3). The strength check ships advisory (D4). The judge prompt and models are frozen before the frozen split is touched (D5). Phase 2 uses at least two model families (D6). Pre-registration goes in a public time-stamped registry before any frozen run (D7). Version one is Python and pytest only (D8). Licensing is decided per corpus source (D9).
- **What the current numbers can claim.** Eleven detections in eleven cases has a lower bound near 72 percent; zero false alarms in eleven clean cases has an upper bound near 28 percent. The three-run behavioral pilot says almost nothing. The claim ledger must keep those intervals in every public sentence until the frozen run lands.
- **Sample-size floors.** At least 36 cases per class to attempt a 90 percent claim at zero errors; plan about 100 per class for the frozen test; at least 45 tasks per arm per model with three runs per task for the behavioral phase. The non-inferiority margin is ten points at roughly 100 positives; five points is out of reach.
- **The demo to build toward.** Two edits with the same surface form and opposite verdicts, each with its evidence. One expected-value change backed by the task text reads CLEAN. One with no support reads TAMPERED or INCONCLUSIVE. That pair demonstrates what a path rule cannot do.
