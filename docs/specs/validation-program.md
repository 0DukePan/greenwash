# Spec: Five-stage validation program with gates A, B and C

Status: ready for agent. Source: the operator's staged validation program, the launch-benchmark spec, and the evidence-verdicts work already merged. New file; it does not replace the launch-benchmark spec.

## Problem Statement

The launch benchmark machinery exists: the launch command decides LAUNCH, NARROW or REFUSED, the corpus kit enforces gate-input hygiene and repository-level splits, the criteria engine evaluates L1 to L9, the claim ledger gates wording, and the reproduction command rebuilds the headline table offline. What does not exist is a corpus anyone can trust, a labeling program that produces it, a baseline comparison on the same inputs, and integration evidence from real pull requests.

Without a staged program, three failure modes are predictable. The frozen split gets opened early, before the detector is worth spending it on. The cases are whatever is convenient to collect, chosen by the tool's own author, and the resulting numbers are self-flattering. Or the launch happens on the planted fixtures, with a claim the ledger does not license. The maintainer needs one written program that says what each stage must produce, which gate decides whether the next stage may start, and exactly what may be said after each one.

## Solution

A five-stage validation program with three gates. Stage 1 builds real cases and trustworthy labels on a development split. Stage 2 attacks the hardest families and publishes a real coverage matrix. Stage 3 compares against strong baselines and returns Gate A, a dev-only decision about whether the frozen split is worth spending. Stage 4 runs the pre-registered benchmark on the sealed split and returns Gate B, LAUNCH or NARROW. Stage 5 integrates with GitHub through shadow, report-only, advisory and required modes and returns Gate C on speed, usability and friction. Every stage names its deliverables, its exit criteria, and the sentences it licenses. Nothing public is said before Gate B.

Agents in this repository build the tooling: the extended case schema, the mining and import paths for the collection routes, the label workflow, the hard-case fixtures and cards, the Gate A and stage-report generation, the GitHub Action and its fork-safe workflows, and the measurement harnesses. The corpus, the labels, the consenting repositories and the usability participants are human work under the operator's control, and the program must never pretend otherwise.

## User Stories

1. As the maintainer, I want each stage to have a written exit criterion, so that starting the next stage is a decision rather than a mood.
2. As the maintainer, I want Gate A decided on the development split, so that the frozen split is only spent on a detector worth testing.
3. As the maintainer, I want the frozen split built last, from repositories never used before, so that leakage is impossible by construction.
4. As the maintainer, I want the pre-registration tag pushed publicly before the first evaluation, so that the commitment is checkable by strangers.
5. As the maintainer, I want every public sentence after each stage checked against the ledger, so that a stage cannot quietly license more than it measured.
6. As the maintainer, I want NARROW planned as a normal outcome with a second-round budget, so that the first frozen result is not treated as a failure to explain away.
7. As the maintainer, I want the assumptions register kept current, so that a number nobody verified cannot end up in a gate.
8. As a collector, I want several independent collection routes, so that no single route's bias becomes the headline.
9. As a collector, I want every case to carry its route, repository, license, refs and diff hash, so that any result can be traced and republished only where licensing allows.
10. As a collector, I want history mining to find assertion changes, deletions and skips alongside code changes, so that real cases exist before any synthetic one is considered.
11. As a collector, I want revert and regression evidence to count as supporting truth, so that a later fix strengthens a label instead of being ignored.
12. As a collector, I want local agent runs on impossible tasks to give labels by construction, so that some positives need no judgment at all.
13. As a collector, I want public dataset cases admitted only where an executable test suite exists and the license is checked, so that the corpus stays usable.
14. As a collector, I want public agent pull requests restricted to licenses that permit it and to no interaction with the repositories, so that the program stays courteous and legal.
15. As a collector, I want every results table split by route, so that a collapse on one route is visible instead of averaged away.
16. As a collector, I want each positive matched to a legitimate twin of the same surface shape with a recorded similarity score, so that false alarms are measured against realistic neighbors.
17. As a collector, I want natural clean and weak-verifier cases in their own classes, so that ordinary output and weak suites are not conflated with tampering.
18. As a collector, I want the five-per-repository cap enforced, so that one project cannot dominate a class.
19. As a labeler, I want to label axes rather than verdicts, so that I never have to claim what an author intended.
20. As a labeler, I want the reference verdict derived mechanically from the axes, so that my gut feeling is measured against a rule, not the other way round.
21. As a labeler, I want a calibration round of twenty cases before the full round, so that the guide is fixed before the expensive work.
22. As a labeler, I want to see the replay result when labeling grade relevance, so that the axis is evidence rather than inference.
23. As a labeler, I want pinned evidence defined as evidence from before the run and never from a file the diff changed, so that spec rewrites cannot launder a case.
24. As an adjudicator, I want disagreements surfaced with both labelers' reasons, so that a third judgment is quick and consistent.
25. As a reviewer, I want raw agreement, kappa and PABAK reported on at least 100 double-labeled cases, so that label noise is measured rather than assumed.
26. As a reviewer, I want the label guide and the corpus datasheet published as deliverables, so that the corpus is reusable and auditable.
27. As a reviewer, I want every miss and every false alarm from the dev measurement classified as implementation bug, taxonomy gap, wrong label or out of scope, so that the next iteration has a target.
28. As a reviewer, I want the coverage matrix statuses backed by dev numbers, so that "covered" is not an opinion.
29. As a reviewer, I want hard-case families with matched evidence and no-evidence versions, so that the hardest decisions are tested deliberately.
30. As a reviewer, I want HC12, pinned but misleading evidence, studied descriptively, so that the tool's worst honest failure is known and written down.
31. As a reviewer, I want the red team to work only on the development split with a fixed attempt budget, so that every evasion becomes a regression test rather than a leak.
32. As a reviewer, I want the evasion success rate reported separately from any gate, so that it informs without contaminating the benchmark.
33. As a reviewer, I want every baseline to see the same inputs with frozen settings and the same tuning budget, so that no comparison is a strawman.
34. As a reviewer, I want the judge to run three times per case with pinned outputs, so that its variance is measured and its cost is comparable.
35. As a reviewer, I want the competitor pinned by version and date and run on the same corpus, so that its self-reported numbers are never the comparison.
36. As a reviewer, I want ablations without replay, without pinned evidence and without the strength flag, so that each component earns its place.
37. As a reviewer, I want Gate A to return go, pivot or stop with the numbers that decided it, so that the decision is auditable.
38. As a reviewer, I want a pivot to change the claims rather than the measurement, so that a close competitor forces honesty instead of moving goalposts.
39. As a maintainer running Stage 4, I want the frozen build to be verified against the dev split and every retired repository, so that overlap refuses rather than warns.
40. As a maintainer, I want the judge run once and pinned before the launch command, so that the offline run reproduces.
41. As a maintainer, I want the launch command's three outcomes mapped to the next step: LAUNCH to integration, NARROW to publish and retire, REFUSED to fix inputs and retry.
42. As a maintainer, I want the narrowed-scope statement and the updated limits page produced from the report, so that a NARROW outcome ships something worth reading.
43. As a beta repository owner, I want shadow mode to run and record without commenting, so that I can review every alert before anyone sees one.
44. As a beta repository owner, I want report-only mode to summarize without failing the job, so that adoption is measurable before it is blocking.
45. As a CI maintainer, I want the action to load the checker and pinned tests from the base ref with hash checks, so that a branch cannot grade itself.
46. As a CI maintainer, I want the workflow to run in `pull_request` with no secrets and read-only permissions, with a separate `workflow_run` posting any comment, so that the well-known token-exfiltration route is closed.
47. As a CI maintainer, I want actions pinned by full commit SHA and permissions minimized, so that supply-chain risk is bounded.
48. As a CI maintainer, I want the static and replay speed measured on five repository sizes with a published cold start, so that the overhead claim has numbers.
49. As a developer in the usability test, I want the verdict first, then the reason, then the evidence, then the next step, so that I know what to do without reading documentation.
50. As a developer, I want INCONCLUSIVE to ask for evidence rather than accuse, so that the tool's uncertainty reads as a request, not a judgment.
51. As a developer, I want the message to say "tests weakened" and never "cheating", so that it claims only what it can see.
52. As a maintainer, I want the unnecessary-interruption rate measured in shadow mode over real pull request history, so that the move to required is evidence-based.
53. As a maintainer, I want a registered threshold and a human approval path before required mode, so that nobody is blocked without recourse.
54. As a reader, I want each stage's allowed wording fixed in advance, so that a partial result cannot be published as a general one.
55. As a reader, I want the fast-path beta clearly priced, so that launching early is a choice with known costs rather than a shortcut.

## Implementation Decisions

### Stage and gate model

- Five stages, three gates, as in the operator's program. Each stage has a goal, work, deliverables, exit criteria and allowed wording. Gates decide only whether the next stage may start; only Stage 4 can license a claim.
- Gate A is dev-only: go to Stage 4, pivot the claims, or stop and improve on dev. Gate B is the launch command's decision. Gate C is speed, usability and friction. Nothing public before Gate B; Stage 5 may run in shadow concurrently from Stage 3 because shadow produces no public artifact.

### Case record

- Extend the corpus record with: `route` (R1 to R5), `base_ref` and `head_ref`, `diff_hash` and optional `diff_path`, `axes` (A mechanism, B grade relevance, C pinned evidence, D harm), `labels` (labeler one, labeler two, adjudicated, disagreement flag), `twin_id` and similarity score, and a `replay` record that is either a recorded hashed result or a sandbox reference. `class` already exists: positive, twin, natural clean, weak verifier. `split` already exists.
- The reference verdict is derived mechanically from axes A to C using the decision table already implemented in the pinned-evidence resolver. Labeler gut-feel verdicts are recorded separately and compared with the derived one.

### Collection routes

- R1 history mining: assertion changes, deletions and skips alongside code changes, found by structural queries and commit-message search. Labeled by people.
- R2 reverts and regressions: later commits that revert the edit or fix a bug tied to it. History evidence supports the label.
- R3 local agent runs on impossible tasks: labels by construction, technique reviewed.
- R4 public datasets: only tasks with an executable suite; licenses checked before anything enters the corpus.
- R5 public agent pull requests: only where the license permits, metadata and diff only, and no interaction with the repository.
- Every table splits by route. A single-route headline is not a result.

### Labeling

- Axes A to D as defined, with axis C requiring evidence from before the run and never from a changed path. Axis D harm uses an independent oracle: reference or upstream first, pinned spec second, a later fix as supporting evidence only.
- Calibration round of twenty cases, then the guide is frozen, then the full round. Two labelers blind to all detector output, a third adjudicates.
- Report raw agreement, kappa and PABAK on at least one hundred double-labeled cases. PABAK at or above 0.70 is the stage exit and the L9 criterion. Labeling time per case is measured in calibration, replacing the fifteen-minute assumption with a measurement.

### Sizes, splits and build order

- Frozen floors: at least one hundred effective positives, twins and natural clean each, at least twenty-four repositories per class, at most five cases per repository; weak verifier at least thirty-six descriptive; at least one hundred double-labeled. Build target two hundred thirty effective for positives and twins. Dev minimum sixty per class, with no gate attached to dev.
- Dev is built first and stays open. Error analysis happens on dev. The frozen split is built last, from repositories never used and never retired, and is hash-locked.

### Hard cases

- Families HC1 to HC12 as listed by the operator, each with a matched evidence and no-evidence version. Tier 1 families named in the README carry at least thirty-six cases each in frozen; Tier 2 families carry at least twelve on dev and are descriptive.
- HC2, HC8 and HC12 are declared limits by design in the limits page, with their observed behavior, rather than hidden or overclaimed. HC11 is the row F case and must set the edited-evidence flag. HC12 is studied descriptively and never used to license a claim.
- The red team works only on dev with a fixed attempt budget and the tool's documentation as input. Every evasion becomes a regression test and a coverage-matrix row. Evasion success is reported separately from every gate.

### Baselines, hypotheses and Gate A

- Baselines B0, B1, B2, B3, the old rule list, the three ablations and the adjudicator-agreement ceiling, all on the same inputs, all settings frozen before the frozen run, equal tuning budget on dev.
- H1 recall versus the judge: non-inferiority at a ten-point margin AND a cost per case at least ten times lower AND reported variance. Either alone is a partial pass reported to Gate A, not a confirmation. H2 twin false alarms versus B0: exact McNemar at the fixed n. H3 expected values versus B3: twin false alarms at least ten points lower with abstention reported. H0, B3 matching Greenwash, triggers the pre-decided pivot.
- Gate A numeric thresholds, fixed before dev is measured: go when H2 is confirmed and H3 holds and abstention is at or below 0.20; pivot when Greenwash and B3 are indistinguishable at the fixed n; stop when recall is clearly lower or abstention is above 0.20. McNemar sample sizes: about fifteen for a large edge, one hundred two for a moderate one, three hundred twenty-two for a small one. Non-inferiority at a ten-point margin needs seventy-nine cases at ten percent disagreement and one hundred fifty-seven at twenty percent; a five-point margin is not promised.

### Stage 4 sequence and outcomes

- Frozen build verified against dev and the retired registry; full labeling with PABAK; the judge run once with outputs and hashes pinned; pre-registration of thresholds hash, detector hash, competitor version and launch configuration inside the manifest, committed and tagged publicly before the first evaluation; the launch command run offline; CI rebuilds and compares byte for byte.
- LAUNCH moves to integration and the ledger's launch wording. NARROW publishes the narrowed-scope statement, retires the repositories, and requires a new frozen split for any detector change. REFUSED fixes the inputs and retries; it is never reported as a result.

### Stage 5 integration

- Forms: a GitHub Action exposing a check run and a job summary, an optional pull request comment via a separate workflow run, a local CLI and pre-commit entry, and agent hooks later.
- Graduated rollout: shadow, then report-only, then advisory, then required with a human approval path. Each transition requires the previous mode's numbers.
- Security: checker, config and pinned tests load from the base ref with hash verification; the analysis workflow runs in `pull_request` with no secrets, read-only permissions and a sandboxed replay; any comment is posted by a separate `workflow_run`; actions pinned by full commit SHA; minimum permissions; no comments on repositories that have not consented.
- Speed: publish static p95 milliseconds, replay overhead as a multiple of the test run, and cold start, measured on five repository sizes. Targets are proposals until measured.
- Usability: a scripted protocol with five to eight developers and eight representative outputs, measuring correct interpretation share and time, with one wording-fix round before the target is checked.
- Friction: shadow replay over merged pull requests in consented repositories, measuring interruption rate, unnecessary interruption, time to resolve, override rate and removal. Required mode needs a registered unnecessary-interruption threshold, every alert hand-reviewed, and a documented approval path.

### Reports, wording and the assumptions register

- Each stage emits a stage report and a machine-readable summary. The allowed-wording table is data checked by the claim ledger, so a stage report cannot license a sentence the ledger forbids.
- An assumptions register lists every unverified number with its owner and how it will be checked: labeling time per case, the speed SLOs, the competitor's overhead figures, and dataset licensing. A gate may not depend on an open assumption.

## Testing Decisions

- **Good tests.** Drive code at its public seam and assert the decision, the report content and the exit code literally. The program's human deliverables cannot be tested by code; the tooling around them can, and must fail closed when data is missing or invalid.
- **Existing seams, preferred.** The corpus kit seam already validates records, splits, caps and gate-input classes, so the extended case schema and its validators are tested there. The launch and evaluation command seams already expose stage-level tables, so Gate A and stage reports are generated and tested through them. The claim ledger seam already gates wording, so each stage's allowed-wording table is a ledger-backed data test.
- **One new seam.** The GitHub Action is tested through its workflow contract: a fixture pull request event, a fork-shaped event, a stub checker result, and assertions on outputs, permissions and the no-comment path. Everything else rides on existing seams.
- **Prior art.** The launch command tests for outcome and refusal coverage, the corpus kit tests for hostile input, the claim ledger tests for planted over-claims, and the reproduction tests for byte identity are the models.
- **Fail-closed rule for tooling.** A missing label, an unverifiable license, an absent replay record for a replay-needing technique, or a route field the miner cannot fill is a rejection naming the field, never a default.

## Out of Scope

- Executing the program: collecting cases, labeling, adjudicating, recruiting repositories and usability participants, and running any model for the judge. Those are operator work; the repository delivers tooling and fixtures.
- Paid model runs. The judge is run once in a pre-registered step and pinned.
- Licensing determinations for R4 and R5 datasets beyond a recorded check that the license permits the use.
- The behavioral Phase 2 study.
- Languages beyond Python and pytest.
- Tuning detectors based on frozen data. That is forbidden by the program itself.
- Marketing copy. This program decides what may be said, not how to say it.

## Further Notes

- **Where I agree with the program as written.** The multi-route structure, axes-not-verdicts labeling, repository-level splits, the dev-open and frozen-sealed order, planned NARROW, the graduated GitHub rollout, the fork-safe workflow shape, and the per-stage allowed wording. All of it is sound and consistent with the launch-benchmark gate.
- **Where this spec tightens it.** H1 now requires both the recall margin and the cost edge; Gate A has numbers instead of adjectives; the assumptions register is mandatory before any gate consumes an assumption; the human-labor boundary is explicit.
- **Current numbers.** The only licensed sentences remain: eleven detections in eleven cases has an exact lower bound of 71.5 percent; zero false alarms in eleven clean cases has an upper bound of 28.5 percent; the planted cases are a plumbing check; the behavior study is inconclusive. The README status line reads `UNMEASURED` until a decision record exists.
- **The fast path is a real choice, priced.** A reduced Stage 1 plus Stage 3 on dev plus Stage 5 report-only can launch a scope-limited beta under the currently allowed wording. It cannot say "detects tampering" or "few false alarms". The price is explicit; the decision is the operator's.
- **Open decisions carried forward.** Full path or fast path; frozen target one hundred or two hundred thirty effective; who labels; the judge; whether the competitor from v4 is the same as B3; the consenting repositories; and the launch configuration. Recommendations from the program are retained: full path, two hundred thirty if achievable, operator plus an independent second labeler plus an adjudicator, one strong judge with a frozen prompt, competitor pinned and confirmed, five to ten consenting repositories, default developer configuration with the conservative policy.
- **Tracker.** The issue tracker and triage labels are not configured in this repository; the spec lives at the path below until `/setup-matt-pocock-skills` is run. The stage reports are repository artifacts, not issues.
- **File.** This spec is at docs/specs/validation-program.md.
