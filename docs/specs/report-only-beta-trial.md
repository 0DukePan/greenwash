# Spec: Report-only beta trial

Status: ready for agent. Source: the validation-program spec (Stage 5), the Phase 1 report's recommendation, and the merged report-only beta path. New file. The dev-corpus-run spec remains the main-path move; this one runs in parallel and needs no corpus.

## Problem Statement

The report-only path exists: a fork-safe workflow that never fails a job, a beta guide, a twin-pair demo, and a friction harness that turns a PR log into five measures. What does not exist is the trial that would use them. The friction harness consumes a PR log nobody can produce yet, and the usability kit has fixtures but no protocol for running a round. So Stage 5's numbers cannot be measured, and the fast-path beta the Phase 1 report recommends cannot be launched with evidence behind it.

The cost of waiting is real: the evidence program takes human weeks, while a report-only beta could measure real interruptions, real interpretation, and real overhead now, and it licenses the only wording available today. The cost of doing it badly is also real: posting comments on repositories without consent, or replaying history with network calls, would be the exact behavior the program forbids.

## Solution

A consented, offline trial. Repositories opt in and record consent. A collector turns each consented repository's merged pull requests into the friction harness's input by replaying the checker against each PR's merge base and head from a local clone, never touching the network and never posting anything. A shadow round produces the five friction measures. A usability round uses the existing kit with five to eight developers and scores interpretation after one wording-fix round. A preliminary Stage 5 report states what was measured, what was not, and that nothing public may be said beyond the claim ledger's current allowed wording.

## User Stories

1. As the maintainer, I want a written consent record per repository, so that no trial ever runs on an unapproved project.
2. As a repository owner, I want to know exactly what the trial does to my history before I agree, so that consent is informed.
3. As the operator, I want to export a repository's merged PR list once, so that the trial can replay it offline.
4. As the operator, I want the collector to refuse a PR whose base or head commit is missing locally, so that a partial clone cannot silently shrink the sample.
5. As the operator, I want the collector to record for each PR whether it touched tests, whether the checker flagged it, and the timestamps it can see, so that the friction harness receives a complete log.
6. As the operator, I want the collector to run the checker against the merge base and head refs, so that replay matches what the checker would have said at the time.
7. As the operator, I want the collector to mark every alert unreviewed by default, so that the human judgment file is the only source of legitimacy.
8. As a reviewer, I want a judgment file that records legitimate or illegitimate per reviewed alert, so that unnecessary interruptions are counted against the change, not the alert.
9. As the operator, I want the friction harness's five measures with explicit denominators, so that a reader can audit every rate.
10. As the operator, I want the trial to state its interruption rate over PRs that touched tests, so that the denominator is never hidden.
11. As the operator, I want unreviewed alerts excluded from the unnecessary count, so that absence of review is not treated as a false alarm.
12. As the operator, I want time-to-resolve computed only where timestamps exist, so that missing data cannot be invented.
13. As the operator, I want override and opt-out events recorded where the repository exposes them, so that friction includes people working around the tool.
14. As the operator, I want a repo with no recorded consent refused by name, so that the trial cannot expand quietly.
15. As the operator, I want the collector to spend a bounded time per PR, so that a pathological diff cannot stall the round.
16. As the operator, I want the collector to run no repository code, so that replaying history never executes untrusted tests.
17. As the operator, I want the trial to run with networking disabled, so that reproduction costs nothing and contacts nobody.
18. As the operator, I want the usability round to use eight fixed outputs and an answer key, so that results across participants are comparable.
19. As a participant, I want each output to show the verdict, the reason, the evidence and the next step, so that I can answer without a briefing.
20. As the operator, I want share-correct and median time computed from responses, so that the 80 percent target is checked mechanically.
21. As the operator, I want one wording-fix round recorded, so that the second measurement is comparable to the first.
22. As the maintainer, I want a preliminary Stage 5 report that separates measured numbers from open questions, so that a partial trial cannot be presented as Gate C.
23. As the maintainer, I want the report to state that Gate C is not decided, so that required mode remains out of reach.
24. As the maintainer, I want the report to name which permitted sentences it licenses, so that any external note stays inside the ledger.
25. As the maintainer, I want the report to record the checker configuration and version used, so that the numbers are attributable.
26. As a repository owner, I want the trial to leave no comments and no check runs on my pull requests, so that opting in has no visible side effects.
27. As a reader, I want the beta guide to explain the trial and how to join, so that recruitment does not depend on a private conversation.
28. As a reader, I want the trial's limitations stated next to its numbers, so that a small sample is not over-read.
29. As a contributor, I want the collector tested against a fixture export and a local clone, so that its behavior is demonstrable offline.
30. As a contributor, I want an out-of-order or incomplete trial step to be a named refusal, so that the fix is obvious.

## Implementation Decisions

- **Consent first.** A consent record names each participating repository, the contact, the date, and the scope (history replay, report-only, no comments). Every trial command reads it and refuses a repository not in it. The record is data, checked into the trial directory.
- **Offline collector.** The collector takes two inputs: a PR export (the metadata a hosting API can produce as JSON, stored as a file) and a local clone containing the merge base and head commits. It replays the checker's static scan per PR against the merge base, records whether the PR touched tests, whether the scan flagged, the timestamps present, and override or opt-out markers if the export carries them. It writes the friction harness's PR-log format. A missing commit, a missing field, or a malformed timestamp refuses by name. No network calls, no repository code, a per-PR time bound, and paths kept inside the clone.
- **Judgment file.** A separate reviewed-alerts file maps PR id to `legitimate` or `illegitimate`, with a reviewer and a date. The term is about the change: legitimate means the alert was a false alarm and the interruption unnecessary; illegitimate means the alert was necessary. Unreviewed alerts are absent from the file and never counted as unnecessary.
- **Friction round.** The existing harness consumes the log and produces interruption, unnecessary interruption, time to resolve, override and removal rates with explicit denominators, its offline statement, and the consent refusal it already enforces.
- **Usability round.** The existing kit supplies the eight outputs, the answer key and the scorer. The trial records participant responses (anonymized ids, answers, seconds) and the one wording revision; the target is checked only after the revision, on the recorded rows.
- **Preliminary report.** A trial report states the participating repositories and their sizes, the PR counts and denominators, the five friction measures, the usability numbers before and after the revision, the checker version and configuration, the measured static overhead per repository, and the open questions. It states in one line that Gate C is not decided and required mode is out of scope. Its licensed-wording section is rendered from the claim ledger; nothing in it may exceed the ledger's allowed wording.
- **No side effects.** The trial never comments, never creates check runs, never pushes, and never writes to a participating repository. The only outputs are local artifacts.
- **Recruitment is human.** The beta guide gains a short "join the trial" section describing the consent, the export, and what the owner receives. Nothing is posted anywhere by the tooling.

## Testing Decisions

- **Good tests.** Drive the collector and the trial report at their public seams and assert the artifacts, the refusals and the numbers literally. Every refusal gets a test that fails if the check is removed.
- **One new seam.** The collector plus trial report over a fixture PR export and a small local clone. The friction harness, the usability scorer and the claim ledger already have their seams and are exercised unchanged.
- **Fixtures.** A two-repository export with a merged PR that touched tests and was flagged, one that did not touch tests, one whose merge base is absent, one with a malformed timestamp, one with an override marker, and a consent record missing the second repository; a judgment file with one legitimate, one illegitimate and one unreviewed alert; a response file for the usability round.
- **Prior art.** The friction harness tests, the usability kit tests, the Gate A refusal tests and the claim-ledger drift test.
- **Fail-closed rule.** Missing consent, missing commit, missing field, malformed timestamp, a repository outside the export, or a report rendered with an unlicensed sentence is a refusal naming the cause.

## Out of Scope

- Posting anything, on any repository, ever.
- Required or blocking mode; Gate C stays undecided.
- The dev corpus, labels, Gate A, Gate B and the frozen split.
- Corpus mining and import routes.
- Paid model runs and any network access at trial time.

## Further Notes

- **Why this is the parallel move.** The Phase 1 recommendation is to start report-only now and defer the frozen split; the main-path spec (`docs/specs/dev-corpus-run.md`) covers the corpus work, which is human weeks. This trial produces Stage 5 evidence in the meantime and runs on the only claims currently licensed.
- **What the trial may say.** Nothing publicly by itself; internally it produces the friction and usability numbers, and any external note is limited to the claim ledger's allowed wording. The launch status remains `UNMEASURED`.
- **Open questions the trial should answer.** How often the checker interrupts PRs that touch tests in consented repositories; how often a human calls the interruption unnecessary; whether developers read the four-part message correctly; and what the static overhead is on real histories, which the Phase 1 measurement only sampled.
- **Tracker.** The issue tracker is not configured; this spec lives at the path below until `/setup-matt-pocock-skills` is run.
- **File.** This spec is at docs/specs/report-only-beta-trial.md.
