# Spec: Launch benchmark and go/no-go decision

Status: ready for agent (revision 2). Source: the v5 plan's launch gate, the evidence-verdicts spec, and the numbers the pages claim today. Replaces `docs/specs/launch-benchmark.md`.

## Revision notes (what changed from revision 1)

| # | Change | Where |
|---|---|---|
| 1 | One **pre-registered launch configuration** decides; other cells are descriptive only | Implementation: Launch configuration |
| 2 | Intervals and sample floors are **repository-cluster aware**; cases per repository are capped | Implementation: Intervals, Sample floors |
| 3 | Designed-for **launch odds** are printed and the floor is chosen knowingly | Implementation: Sample floors; Further Notes |
| 4 | Pre-registration and "fresh split after a failed gate" are **mechanisms with tests**, not policy | Implementation: Pre-registration and burn rule |
| 5 | **Refusal is not a decision.** Three distinct exit outcomes; sample floor is a criterion (NARROW), not a refusal | Implementation: Outcomes |
| 6 | Fail-closed rule, exact **boundary pins**, and **all** failing criteria named | Testing Decisions |
| 7 | New tests: offline enforcement, hostile repository content, LF-only byte-stable output | Testing Decisions |
| 8 | Conservative rounding, abstention ceiling and label-quality criterion given values, ledger-test limits stated | Implementation; Further Notes |

## Problem Statement

Greenwash's central claim is that a passing test suite is not evidence until something checks the suite itself. The evidence behind that claim is first-party and small. The planted corpus reports 24 of 24 cheats caught and 0 false positives on 24 honest fixes. The tampering corpus reports 11 of 11 detections and 0 of 11 twin false alarms, with exact intervals that still allow a true detection rate as low as 71.5 percent and a true false-alarm rate as high as 28.5 percent. The 252-run behavior study observed no cheating, so it cannot support a behavioral claim at all. The false-positive survey covers three repositories.

A GitHub launch asks strangers to install a gate on their pull requests. That deserves evidence on inputs the maintainers did not author: real test edits from real histories, real tampered diffs, and the detector's behavior on both. Nobody has run that measurement at a size the intervals can support. Worse, there is no written rule that says when the evidence is good enough. Without a rule, the launch decision is taste, and the claim ledger becomes decoration. The maintainer needs one benchmark that answers a single question: does this tool do its job well enough that a public launch is defensible, and if not, what may still be said?

## Solution

A launch benchmark with a pre-registered go/no-go. A frozen, human-labeled corpus is built from real repository history and local agent runs, split by repository so nothing in development can leak into the evaluation. The detector and its three baselines run over that corpus through the existing evaluation runner. A launch gate, committed before the frozen corpus is first evaluated, turns the per-cell numbers into exactly two decisions: LAUNCH, when every criterion holds, or NARROW, when any one fails. Inputs that cannot be trusted produce a third thing that is not a decision: a REFUSED run with no decision record.

The launch report states the decision, prints the interval on every headline number, names every failing gate, and pairs each public sentence with the strongest wording the claim ledger allows. If the answer is NARROW, the report still publishes the measured limits and the narrowed scope instead of the claim.

## User Stories

1. As the maintainer, I want one command that runs the launch benchmark end to end, so that the decision never depends on a hand-assembled spreadsheet.
2. As the maintainer, I want the go/no-go criteria written down and committed before the frozen corpus is first evaluated, so that I cannot move the goalposts after seeing the numbers.
3. As the maintainer, I want exactly two possible decisions, so that a partial pass cannot be narrated as a win.
4. As the maintainer, I want every failing gate named with the number that failed it, so that the next iteration starts from evidence rather than intuition.
5. As the maintainer, I want the benchmark to refuse to run on drifted frozen artifacts, so that a stale corpus cannot produce a fresh-looking decision.
6. As the maintainer, I want every headline number to carry its exact interval, so that the launch announcement cannot quote a point estimate.
7. As the maintainer, I want the abstention rate reported beside recall and held to its own ceiling, so that refusing to decide is visible and never counted as accuracy.
8. As the maintainer, I want the corpus split by repository, so that a task seen in development never appears in the frozen evaluation.
9. As the maintainer, I want the corpus to exclude the planted fixtures from any gate, so that a detector designed against its own taxonomy cannot flatter itself.
10. As the maintainer, I want per-cell results by source, technique and language, so that one pooled rate never hides where the tool fails.
11. As the maintainer, I want the false-alarm rate measured on real legitimate test edits, so that the number I publish matches what users will experience.
12. As the maintainer, I want the recall measured on real tampering from independent sources, so that the headline is not a test of the test author.
13. As the maintainer, I want labels produced blind by two people with adjudication, so that label noise is measured rather than assumed.
14. As the maintainer, I want raw agreement, kappa and PABAK reported, so that skewed prevalence cannot make agreement look better than it is.
15. As the maintainer, I want the benchmark to record runtime and cost per case, so that the adoption story is honest about the price.
16. As the maintainer, I want a pre-registered determinism rule (every frozen case, or a stated stratified sample with its bound), so that a result cannot come from a lucky run.
17. As the maintainer, I want the report to list every artifact with its hash, so that a reader can tie the decision to exact inputs.
18. As the maintainer, I want the launch report to render its claim table from the ledger, so that no sentence in the announcement exceeds the evidence.
19. As the maintainer, I want a NARROW outcome to produce a publishable narrowed-scope statement, so that a failed launch gate still leaves useful work to show.
20. As the maintainer, I want the benchmark to mechanically refuse a second evaluation of the same frozen split with a changed detector, and to retire every repository a failed split used, so that re-testing cannot quietly inflate a result.
21. As a reader of the launch post, I want the headline claim to come with its sample size and interval, so that I can judge it without downloading the repo.
22. As a reader, I want the limits page to state what the benchmark did not cover, so that I do not adopt the tool for the wrong job.
23. As a reader, I want the launch report linked from the README methods section, so that the public numbers are one click from their evidence.
24. As a reader, I want the benchmark to name the corpora's provenance and licenses, so that I know what may be reused.
25. As an early adopter, I want the launch decision to separate detection quality from behavior change, so that installing the gate is not sold on an unmeasured behavioral effect.
26. As an early adopter, I want the false-alarm rate on justified test edits spelled out with its interval, so that I can estimate how often the gate will ask me to explain myself.
27. As an early adopter, I want the abstention behavior documented, so that I know when the tool will say it cannot decide.
28. As an early adopter, I want the changed-expected-value handling demonstrated on a real twin pair, so that I can see the hardest case working.
29. As a reviewer of the launch PR, I want the benchmark to reproduce from pinned artifacts with no model in the loop, so that I can verify the table myself.
30. As a reviewer, I want the launch report to be regenerated by CI and compared byte for byte, so that a hand-edited report fails the build.
31. As a reviewer, I want the decision rule's thresholds in one data file, so that a threshold change is a visible diff.
32. As a reviewer, I want the benchmark to record the detector configuration used for every cell, so that results are attributable to a version.
33. As a security-conscious team lead, I want the benchmark to run offline with recorded outputs for anything that needs a judge, so that reproducing it costs nothing and contacts no one.
34. As a security-conscious team lead, I want the corpus builder to treat repository content as untrusted input, so that the benchmark itself cannot be steered by the data it measures.
35. As a contributor, I want a failing gate to say which corpus cell would move the decision, so that improvement effort is aimed.
36. As a contributor, I want the dev split to be open and the frozen split sealed, so that I can iterate without burning the evaluation.
37. As a contributor, I want the corpus record schema and label protocol documented, so that adding cases does not require reading the code.
38. As a contributor, I want the benchmark's own tests to prove both outcomes, LAUNCH and NARROW, so that neither branch is theoretical.
39. As a maintainer preparing the announcement, I want the report to print the exact allowed wording for each claim, so that drafting is a copy step rather than a negotiation.
40. As a maintainer, I want the launch checklist in the docs to point at the report's decision line, so that publishing requires a measured yes.
41. As a maintainer, I want the benchmark to state the sample it was designed for and the odds of LAUNCH that design implies, so that a corpus too small to support a claim is caught before the run.
42. As a reader of the repository, I want the current launch status shown in the README, generated from the decision record, so that a visitor knows whether the claim is supported yet.
43. As the maintainer, I want exactly one launch configuration pre-registered as the decider, so that I cannot pick the best of four detector cells after seeing results.
44. As a reader, I want every headline to show the number of cases and the number of distinct repositories behind it, so that "100 cases" is not secretly three projects.
45. As a reviewer, I want intervals that account for repository clustering, so that correlated cases cannot make the evidence look tighter than it is.
46. As the maintainer, I want REFUSED, NARROW and LAUNCH to be distinguishable by exit code and by artifacts, so that CI can never read a refusal as a publishable result.
47. As a reviewer, I want the pre-registration record to be committed, and ideally tagged publicly, before the first frozen evaluation, so that the commitment is checkable by outsiders.
48. As the maintainer, I want every bound rounded in the conservative direction, so that no printed number flatters the tool.
49. As the maintainer, I want label quality to be a criterion, not only a report, so that a corpus labeled too noisily cannot license a claim.
50. As a reviewer, I want the report and decision record to be byte-identical across operating systems, locales, time zones and line-ending settings, so that reproduction does not depend on my machine.
51. As a contributor, I want a failing run to list every failing criterion in a fixed order, so that fixing one does not hide the next.

## Implementation Decisions

### Outcomes and exit codes

- **Two decisions, one non-decision.** The launch command returns LAUNCH only when every criterion holds, and NARROW otherwise. There is no third decision and no free-text verdict.
- **Exit codes.** `0` = LAUNCH, `1` = NARROW (report and decision record written; publishable), `2` = REFUSED (input or pre-registration failure; **no decision record, no report headline**). Usage errors use a different range. The implementer may remap numbers to fit existing conventions, but the three-way distinction must survive and be tested.
- **Fail closed.** A criterion that cannot be evaluated (missing cell, empty class, NaN, interval not computable, check that did not run) is a **failed** criterion with reason `not evaluated`, which yields NARROW. It is never skipped and never treated as passing.
- **What refuses (exit 2):**
  1. any frozen artifact hash differs from the frozen manifest;
  2. the thresholds-file hash differs from the pre-registration record;
  3. the launch configuration or detector hash differs from the pre-registration record;
  4. the frozen manifest has already been evaluated with a different detector hash (a fresh split is required);
  5. a gate input record is planted, synthetic, from the dev split, or lacks source, repository identity, license, technique or split;
  6. any attempted network access;
  7. a baseline pin (including the competitor version) is missing or unverifiable.
- **Sample floor is a criterion, not a refusal.** A corpus below the floor yields NARROW naming the floor, because the report is still publishable as a limits statement.

### Gate as data

The launch criteria live in one versioned data file. Changing a threshold is a one-line diff, and any change after pre-registration is caught by refusal 2. Defaults below are proposals; each judgment-call value is listed in Further Notes and must be fixed **before** the freeze.

| ID | Criterion | Default threshold | Evaluated on |
|---|---|---|---|
| L1 | strict recall, lower bound | ≥ 0.90 | launch configuration; real in-scope positives; gate-deciding interval |
| L2 | twin false alarms, upper bound | ≤ 0.10 | launch configuration; real legitimate twins |
| L3 | abstention ceiling, upper bound | ≤ 0.20, checked separately on twins and on natural clean passes | launch configuration |
| L4 | determinism | zero byte differences over 5 runs of every frozen case, or of a pre-registered stratified sample of at least 100 cases covering every technique cell | launch configuration |
| L5 | integrity | integrity suite ran, and zero successful modifications | checker, config and pinned tests |
| L6 | reproducibility | offline rebuild from pinned artifacts is byte-identical to the committed report and decision record | whole pipeline |
| L7 | ledger coverage | the announcement draft contains no claim outside its row's allowed wording, and every claim sentence maps to a ledger row | announcement draft, ledger |
| L8 | sample floor | effective n ≥ 100 per class (positives, twins, natural clean), at least 24 distinct repositories per class, at most 5 cases per repository | frozen corpus |
| L9 | label quality | at least 100 double-labeled cases and PABAK ≥ 0.70; kappa and raw agreement reported | double-labeled sample |

Strict recall counts an abstention on a positive as a miss. Decided-case recall is reported beside it but never gates.

### Launch configuration

- The pre-registration record names **one** launch configuration (proposed: the default developer configuration with the conservative expected-value policy). **L1-L5 are evaluated on that cell only.**
- The strict configuration, the strict expected-value policy and the baselines are reported in the same table as descriptive cells. They cannot rescue a failed gate and cannot fail one.
- Changing which cell decides changes the thresholds-file hash, which triggers refusal 2.

### Pre-registration and burn rule

- **Pre-registration record**, stored inside the existing frozen manifest (no new command): thresholds-file hash, launch configuration id, detector configuration hash and version, pinned baseline versions (including the competitor), taxonomy version, tool commit, frozen manifest hash.
- **Order.** The record is committed before the first evaluation of the frozen split. The recommended practice is a signed tag pushed publicly at that point; the public tag, not the local file, is what outsiders can check.
- **Evaluation ledger.** An append-only, hash-chained list of `(manifest hash, detector hash, thresholds hash, decision)`. The first evaluation of a manifest appends an entry. A rerun with identical hashes is allowed and must reproduce the same decision and bytes. A rerun with a different detector hash is refusal 4.
- **Retired repositories.** After any evaluation, every repository in that frozen manifest is added to a retired registry. The corpus kit rejects any new frozen split that reuses a retired repository, and any frozen repository that appears in the dev split.
- **Honest limit.** The ledger is tamper-evident through git history, not tamper-proof. The publicly pushed pre-registration tag is the real commitment.

### Intervals, rounding and clustering

- **Primary interval:** exact Clopper-Pearson, two-sided 95%. **Sensitivity column:** Wilson. **Clustering column:** see below. No pooled number is printed without its cells.
- **Repository clustering.** Cases from one repository are correlated, so case-level exact intervals are optimistic.
  - The corpus kit enforces a cap of 5 cases per repository per class.
  - The gate computes a design effect `DEFF = 1 + (m̄ − 1) · ρ`, where `m̄ = Σ mᵢ² / Σ mᵢ` over repository cluster sizes `mᵢ`, and `ρ = max(ρ̂, ρ_floor)` with `ρ̂` the ANOVA intraclass-correlation estimate of per-case correctness by repository and `ρ_floor = 0.05`.
  - Effective counts are `n_eff = n / DEFF` and misses scaled by the same factor. **The gate-deciding interval is the exact Clopper-Pearson bound at the effective counts**, which is never tighter than the case-level bound because `DEFF ≥ 1`.
  - Every headline table shows `n_cases`, `n_repos`, `ρ̂`, `ρ_used`, `DEFF`, `n_eff`, and both intervals.
- **Conservative rounding.** One decimal place; lower bounds round down, upper bounds round up. Example: 11 of 11 gives a lower bound of 71.5%; 0 of 11 gives an upper bound of 28.5%.

### Sample floors

- The floor is the number the interval arithmetic requires, expressed in **effective** n. With zero errors, 36 cases per class would reach a 90% bound; with up to four errors the requirement is 100 effective cases, and that is the default floor.
- At `ρ_floor = 0.05` and a cap of 5, the worst-case design effect is 1.2, so the default floor is about 120 cases from at least 24 repositories per class.
- **The report prints the designed-for table** (below) from the same arithmetic, so a reader sees the odds of LAUNCH the sample implies. Recommended build target, if achievable: 230 effective cases for positives and twins.

| Effective n per class | Max errors for a 90% bound | P(LAUNCH-eligible) if true rates are 99% / 1% | 97% / 3% | 95% / 5% |
|---|---|---|---|---|
| 100 | 4 | 99.3% | 66.9% | 19.0% |
| 230 | 13 | 100% | 98.0% | 54.3% |

(Probability that both L1 and L2 pass, assuming the two classes are independent and effective cases are independent; other criteria can only lower it.)

### Labels

- Two labelers annotate blind to detector output; a third adjudicates. The report includes raw agreement, kappa and PABAK on the double-labeled sample. L9 makes the count and PABAK floor a criterion. Reference points for PABAK from the plan's source audit were 0.74 and 0.69, which is why the default is 0.70.
- Gates are computed on the adjudicated labels. The report also prints a label-noise sensitivity: the gate numbers with every case that had labeler disagreement flipped against the detector. This is descriptive and never gates.

### Corpus provenance and hygiene

- Positives come from real repository histories and local agent runs, not from planted fixtures. Planted and synthetic cases remain loadable and are reported separately as plumbing, never as gate inputs (refusal 5 enforces it).
- Every record carries source, repository identity, license, technique from the versioned taxonomy, and split.
- **Untrusted input.** The corpus builder reads repository objects only. It never executes repository code, hooks or filters, never honors repository-supplied git configuration, rejects paths that escape the work tree, and bounds file sizes and counts. Any case needing replay runs in the integrity-checked sandbox (no network, no secrets, resource limits) or uses a recorded, hashed replay result stored in the record.

### Baselines and metrics

- The existing adapters for the path rule, held-out tests, the judge and the pinned competitor run over the same records. Anything requiring a model is run once in a pre-registered step and its outputs are pinned; the launch command itself runs offline.
- Metrics: strict recall and decided-case recall, twin and natural false alarms, abstention, per-cell breakdowns by source, technique and language, cost and wall time, and run-to-run variance.

### Decision inputs and outputs

- The launch gate consumes only the evaluation runner's computed table, the pre-registration record and the claim ledger; it reads no prose.
- **Outputs**, all generated, never typed: a human-readable launch report and a machine-readable decision record under the results tree. The decision record lists `decision`, `deciding_criterion` (the first failing criterion in fixed order), `failing_criteria` (all of them), per-criterion value, threshold, interval and effective n, configuration ids, artifact hashes, and the pre-registration hash.
- **Byte stability.** LF line endings only (pinned in `.gitattributes` for the results tree and spec files), fixed locale and time zone, sorted keys, fixed numeric formatting. The human report contains no timestamps; the decision record's single `generated_at` field is excluded from the byte comparison **by field name**, never by pattern. CI rebuilds and compares; a hand-edited report fails.

### Claim coverage and failure path

- The report's announcement-wording section is rendered from the ledger. A claim whose status is not supported may appear only in the "may not say" column, and the gate fails L7 if the announcement draft contains any of it.
- **Limit of the check.** The ledger test matches registered claims and their registered variants. It proves the gate catches those; it does not prove no paraphrase escapes. Announcement review stays human, and each ledger row should list several phrasings.
- **NARROW** produces a narrowed-scope statement: the coverage matrix, the measured false-alarm rate with its interval, and the abstention rate, each with the ledger's allowed wording. This is a publishable artifact, not an error.
- **README status line**, generated from the decision record and checked by CI: `UNMEASURED` (no decision record), `NARROWED` (naming the failing criteria), or `LAUNCH-READY`.

## Testing Decisions

- **Good tests.** Drive the command as a user would and assert the decision, exit code, failing criteria and reported numbers literally. No assertions on internal call order. Every branch with a decision must have a test that would fail if that branch were removed.
- **Existing seams, preferred.** The evaluation runner's fixture-corpus seam and interval tests, the reproduction command's byte-identical rebuild seam, the claim ledger's docs-pin seam, and the corpus kit's split-enforcement seam. The launch command is **one new seam** over all of them and adds no other public surface.

| # | Test (through the launch command unless noted) | Asserts |
|---|---|---|
| T1 | all criteria forced to pass | LAUNCH, exit 0 |
| T2 | each of L1-L9 forced to fail, one at a time | NARROW, exit 1, names exactly that criterion |
| T3 | two or more criteria failing | NARROW; `failing_criteria` lists all, `deciding_criterion` is the first in fixed order |
| T4 | boundary pins | n = 100: 4 misses gives lower bound 0.9007 (pass), 5 misses gives 0.8872 (fail); 4 twin false alarms gives upper bound 0.0993 (pass), 5 gives 0.1128 (fail); zero errors: n = 36 gives 0.9026 (pass), n = 35 gives 0.89997 (fail) |
| T5 | remove each input in turn (a cell, a class, an artifact the check needs) | NARROW with reason `not evaluated`, never LAUNCH |
| T6 | each of refusals 1-7 | exit 2, no decision record, no report headline |
| T7 | launch twice on one manifest: same hashes, then a changed detector hash | first rerun reproduces identical bytes; second is refusal 4. A new split reusing a retired repository is rejected by the corpus kit |
| T8 | change the launch configuration or any threshold after pre-registration | refusal 2 or 3 |
| T9 | a non-launch cell passes while the launch cell fails | NARROW |
| T10 | fixture where case-level interval passes but the effective-n interval fails | NARROW |
| T11 | corpus kit: a repository with more than 5 cases in a class | rejected or capped, per the builder's contract |
| T12 | add planted or synthetic records to a class | refusal 5 when in gate inputs; identical gate numbers when kept out |
| T13 | abstention above its ceiling on twins, then on natural clean | NARROW naming L3 each time |
| T14 | double-labeled count below floor; PABAK below floor | NARROW naming L9 |
| T15 | report rebuilt twice; rebuilt under a different locale, time zone and CRLF checkout; committed report compared with a fresh rebuild | byte-identical; a hand-edited report fails |
| T16 | planted over-claim in the announcement draft, and a registered paraphrase of it | L7 fails both times |
| T17 | block all network access during the run | still passes; any connection attempt fails the test |
| T18 | corpus kit (existing seam): hostile fixture repositories (symlink escape, path traversal, executable hooks, repository-supplied git config, oversized files, control characters in filenames) | a canary file is never created, nothing outside the work tree is touched, bad inputs are rejected |
| T19 | rounding | 11 of 11 prints 71.5; 0 of 11 prints 28.5; lower bounds never round up |
| T20 | README status line | `UNMEASURED` with no record, `NARROWED` after a NARROW fixture, `LAUNCH-READY` after a LAUNCH fixture; CI fails if the committed line differs |

- **Prior art.** The evaluation runner's fixture tests, the reproduction command's determinism test, and the claim ledger's planted-violation test are the models to follow.

## Out of Scope

- Paid model runs. Anything requiring a judge is run once, pre-registered, with outputs pinned.
- The behavioral Phase 2 study. The protocol runner exists; running it is a separate decision, and the launch gate does not depend on it.
- Languages beyond Python and pytest.
- New detectors or rule tuning inside this work.
- Rating or comparing other tools beyond the pinned competitor baseline.
- Publishing third-party repository content. Where licenses forbid, only labels, hashes and aggregate results are published.
- The marketing itself: this spec decides whether a launch claim may be made, not how to make it.

## Further Notes

- **The decision rule, restated.** Launch only if, on the pre-registered launch configuration, strict recall's lower bound and the twin false-alarm upper bound hold under the cluster-aware interval, abstention is under its ceiling, determinism and integrity pass, label quality passes, the report reproduces from pinned artifacts, the ledger covers the announcement, and the corpus meets its floor. Any failure means NARROW, and the narrowed report ships instead. Any untrustworthy input means REFUSED, and nothing ships.
- **What today's numbers can support.** These sentences are the current allowed wording and must appear unchanged until the launch benchmark replaces them. The only permitted edit before then is the conservative rounding fix: "Eleven detections in eleven cases has an exact 95% lower bound of 71.5 percent. Zero false alarms in eleven clean cases has an exact 95% upper bound of 28.5 percent. The 24 planted cases are a plumbing check, not evidence. The 252-run behavior study is inconclusive on behavior."
- **Sample arithmetic.** About 36 per class at zero errors to attempt a 90 percent claim (35 falls just short at 0.89997); 100 effective cases to survive up to four errors; a design effect applied for repository clustering; a double-labeled sample of at least 100 so agreement is measured rather than guessed.
- **Expect NARROW on the first run.** Even a very good detector (97% / 3%) clears both gates only about two times in three at 100 effective cases. NARROW is a planned, publishable outcome, not a failure; the corpus, the limits and the measured false-alarm rate are the deliverable either way.
- **Judgment-call values to fix before the freeze** (they are proposals, not derived): the abstention ceiling (0.20), the PABAK floor (0.70), the per-repository cap (5), `ρ_floor` (0.05), the determinism rule (every case or a stratified sample), the floor (100 versus the 230 build target), and which configuration is the launch configuration.
- **Tracker.** The issue tracker and triage labels are not configured in this repository. The spec lives at the path below until `/setup-matt-pocock-skills` is run; the launch report itself is a repository artifact, not an issue.
- **File.** This spec is at docs/specs/launch-benchmark.md.
