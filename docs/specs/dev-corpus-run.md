# Spec: Dev-corpus run pipeline

Status: ready for agent. Source: the validation-program spec, the Phase 1 report's halved recommendation, and the eight tool tickets now merged. New file.

## Problem Statement

Every tool the halved Stage 1 needs now exists: history miners, importers, the v2 case record with gate admission, the label workflow, twin matching, hard-case cards, the shadow harness, and the Gate A report. What does not exist is the run itself. Assembling a development corpus today means invoking six tools in the right order, keeping their files consistent by hand, remembering which records are unadjudicated, and hoping the cap, deduplication and class balance were respected. A single mistake is invisible: a duplicated diff inflates a class, an unadjudicated case slips into an evaluation, or Gate A runs on a table produced from a corpus nobody can reconstruct.

The assumptions register is honest but inert. Labeling time and competitor overhead are marked open, and Gate A correctly refuses while they are open. Nothing in the tooling can close them from a measurement, so a human must hand-edit the register, which is exactly the kind of unverifiable step the program exists to avoid.

The next move is therefore not more collection tooling. It is a pipeline that runs the dev stage end to end, makes the human steps explicit checkpoints, and closes assumptions only from recorded measurements.

## Solution

One dev-run pipeline with ordered checkpoints. It assembles validated candidate records into a balanced development split, records the calibration measurement, walks the human labeling and adjudication steps as explicit gates, pairs twins, runs the detector over the dev split, and hands Gate A a table plus a complete provenance trail. Every checkpoint writes a pinned artifact; every step refuses to run out of order or on incomplete input. No step can be skipped silently, and the pipeline's final state says exactly which step is next and why.

Assumptions close only through evidence: the calibration checkpoint may mark labeling time verified with its measured value and the artifact that measured it, and the baseline checkpoint may close the competitor-overhead assumption. A hand-edited register without evidence is refused.

## User Stories

1. As the maintainer, I want one command that shows the current dev-run step and the next required action, so that the sequence is never held in my head.
2. As the maintainer, I want assembly to reject duplicates by diff hash, so that one change cannot inflate two classes.
3. As the maintainer, I want assembly to enforce the five-per-repository cap and report class balance, so that the dev split is not secretly three projects.
4. As the maintainer, I want every assembled record to be unadjudicated, so that a proposal can never enter an evaluation as a label.
5. As the maintainer, I want the dev split manifest recorded and versioned, so that any dev run can be reconstructed without sealing it.
6. As the maintainer, I want calibration to measure time per case and close the labeling-time assumption with that measurement, so that the register reflects evidence rather than memory.
7. As the maintainer, I want labeling packets generated only after calibration closes, so that the guide is fixed before the expensive work.
8. As a labeler, I want my packet to contain no detector output and no other labeler's answer, so that my judgment is independent.
9. As an adjudicator, I want disagreements surfaced with both reasons and a single adjudication record, so that the label set is complete and auditable.
10. As the maintainer, I want the pipeline to refuse the evaluation step while any case lacks adjudication, naming the cases, so that labels cannot be defaulted.
11. As the maintainer, I want twins matched after labels exist, so that a legitimate record is known to be legitimate before it is used as a negative.
12. As the maintainer, I want the detector run over the dev split to produce the evaluation table Gate A consumes, so that the two cannot disagree about the input.
13. As the maintainer, I want Gate A to consume only pipeline artifacts, so that a hand-assembled table cannot reach the decision.
14. As the maintainer, I want the baseline step to close the competitor-overhead assumption with the measured figures, so that Gate A's cost comparison rests on a measurement.
15. As the maintainer, I want each checkpoint to refuse when its input is stale or missing, naming the artifact, so that a rerun cannot mix old and new data.
16. As the maintainer, I want a summary of what ran, with counts per route and class, so that the dev corpus describes itself.
17. As a reviewer, I want every checkpoint artifact to carry its input hashes, so that a dev result can be traced without trusting the tool.
18. As a reviewer, I want the pipeline to state that dev results license no public claim, so that a dev number cannot be quoted as performance.
19. As a contributor, I want the pipeline to run on a fixture corpus end to end, so that its behavior is demonstrable before real data exists.
20. As a contributor, I want assembly to accept records from miners and importers interchangeably, so that routes are not special-cased.
21. As a contributor, I want an out-of-order step to be a named refusal, so that the fix is obvious.
22. As a contributor, I want the split layout documented, so that adding cases does not require reading code.
23. As the maintainer, I want the pipeline to record the detector configuration it used, so that a dev number is attributable to a build.
24. As the maintainer, I want the run to state its total labeling time from calibration, so that the human cost is a measured number.
25. As the operator, I want the pipeline to stop at the labeling checkpoint and wait for human files, so that automation never pretends to label.
26. As the operator, I want to resume at any checkpoint after supplying its inputs, so that a multi-day task is not one sitting.
27. As the operator, I want a refusal if I supply label files with case ids outside the split, so that stale files cannot contaminate a run.
28. As the operator, I want the register to show which assumptions Gate A still needs, so that I know exactly what must close before the decision.
29. As the maintainer, I want Gate A to run only when every consumed assumption is verified with evidence, so that the decision is never made on faith.
30. As the maintainer, I want a pipeline report beside Gate A's report, so that the decision cites the run that produced it.

## Implementation Decisions

- **One command, ordered checkpoints.** A dev-run command exposes the stages `assemble`, `calibrate`, `label`, `adjudicate`, `twins`, `baselines`, `evaluate`, and `gate-a`. Each stage checks the artifacts of its predecessors, refuses out of order by name, and writes its own artifact under the dev-run directory. A bare invocation prints the current state and the next required stage. Resume is the same command re-run.
- **Dev split, not a frozen split.** Assembly writes a dev manifest with input hashes and the record set, versioned and mutable by design. It never marks anything frozen, and the frozen refusal in Gate A remains the backstop.
- **Assembly rules.** Deduplicate by diff hash across routes, keep the five-per-repository cap per class, require a route and a technique per record, keep every record unadjudicated, and print counts by route and class. A class under the dev minimum is warned about, not silently accepted.
- **Calibration closes an assumption.** The calibrate stage measures time per case, writes the measurement artifact, and updates the assumptions register with status `verified`, the measured number and the artifact path. Manual edits to an open assumption without an evidence path are refused by the existing register loader, which gains an evidence field.
- **Labeling and adjudication are human checkpoints.** The pipeline generates blind packets, then waits. Supplied label files are validated against the split; adjudication is recorded once per case; the evaluate stage refuses while any case lacks an adjudicated label, naming the cases.
- **Twin step.** Twins are matched only from adjudicated legitimate records after labeling, and the pair list becomes an input to the evaluation table.
- **Baseline step.** The pinned competitor and the other baselines run on the dev split; the measured cost and overhead figures close the competitor-overhead assumption.
- **Evaluation step.** The detector runs over the dev split through the existing evaluation runner via a record adapter, producing the table Gate A already consumes. The detector configuration id and hash are recorded.
- **Gate A consumes pipeline artifacts only.** It reads the pipeline's evaluation table, labelled cases, baselines and register; a table from outside the pipeline is refused by a provenance check.
- **Provenance everywhere.** Every artifact carries the hashes of its inputs; a stale artifact is a refusal, never a silent reuse.
- **What dev may say.** The pipeline report states in one line that development results are not evidence of generalization and may be quoted only as case counts and labeled dev numbers.

## Testing Decisions

- **Good tests.** Drive the command at its public seam and assert the stage outcome, the refusal, and the artifact contents literally. Each order violation and each incomplete-input case gets a test that fails if the check is removed.
- **One new seam.** The dev-run command over a fixture corpus, from assembly to a Gate A fixture decision. Existing seams do the rest: the corpus kit for records and caps, the label workflow for packets and agreement, the evaluation runner for the table, the Gate A report for the decision, and the assumptions register for evidence-backed closure.
- **Fixtures.** A small set of candidate records spanning two routes, one duplicate, one over-cap repository, one unadjudicated case, one synthetic record, and twin candidates; a calibration file with measured times; two label files with a disagreement and an adjudication.
- **Prior art.** The launch command's checkpoint and refusal tests, the Gate A fixture suite, the corpus kit's hostile-input tests, and the reproduction determinism tests.
- **Fail-closed rule.** Missing artifact, stale hash, out-of-order stage, unknown case id, unadjudicated case, or a register assumption closed without evidence is a refusal naming the cause.

## Out of Scope

- Collecting real cases or doing the labeling. The pipeline stops and hands those to humans.
- The frozen split, pre-registration and the launch command. Those remain Stage 4 and are unchanged.
- Stage 2's full family expansion and the red team.
- New detectors or thresholds.
- Publishing anything. Dev results license case counts and dev-labeled numbers only.

## Further Notes

- **Current state.** All eight tool tickets are merged on `spec/validation-program`; the suite is green at 889 collected. The assumptions register currently holds labeling time, competitor overhead and Stage 5 speed targets, the last scoped to Gate C. Gate A refuses on the two open gate-a assumptions, as designed.
- **Sizing.** The halved recommendation stands: sixty per class for dev, calibration on twenty cases, then declare Stage 1 complete and run Gate A.
- **What this unlocks.** With the pipeline, the operator's remaining work is collection and labeling; everything between those and a Gate A decision is one resumable command with an audit trail.
- **Tracker.** The issue tracker is not configured; this spec lives at the path below until `/setup-matt-pocock-skills` is run. Tickets would follow under the same local convention.
- **File.** This spec is at docs/specs/dev-corpus-run.md.
