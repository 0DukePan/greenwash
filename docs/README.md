# What is in `docs/`

Twenty-three documents, and no reason for a reader to guess which one answers
their question. This page is the map.

## If you are deciding whether to use it

| Question | Read |
|---|---|
| What does it actually measure? | [benchmark-summary.md](benchmark-summary.md) -- one page, every number with its interval |
| Can I check the claim myself? | [benchmark-for-readers.md](benchmark-for-readers.md) -- one command, ninety seconds, no model |
| What has it missed? | [what-did-not-work.md](what-did-not-work.md) -- the failures, the misses, the open gaps |
| What is it not allowed to claim? | [claim-matrix.md](claim-matrix.md) -- every public sentence and its evidence class |
| What does a false positive look like? | [false-positives.md](false-positives.md) and [false-positive-survey.md](false-positive-survey.md) |
| How do I adopt it without breaking my team? | [ADOPTION_GUIDE.md](ADOPTION_GUIDE.md) |

## If you are reading a report

| Question | Read |
|---|---|
| What does CLEAN mean, exactly? | [confidence.md](confidence.md) -- the decision table and the arithmetic |
| How is strict mode different from report mode? | [report-vs-strict.md](report-vs-strict.md) |
| How do I resolve a finding without hiding it? | [WAIVER_POLICY.md](WAIVER_POLICY.md) |
| How do I read the numbers in a benchmark table? | [RESULT_INTERPRETATION.md](RESULT_INTERPRETATION.md) |
| What do the error codes mean? | `README.md`, the exit-code table |

## If you are auditing the project

| Question | Read |
|---|---|
| What is the threat model? | [threat-model.md](threat-model.md) -- and `THREAT_MODEL.md` at the root |
| What was the phase-1 hardening? | [phase1-report.md](phase1-report.md) |
| What did the internal review find? | [audit.md](audit.md) |
| How is this repository maintained by one person? | [maintenance.md](maintenance.md) |
| How is a release cut? | `RELEASING.md` at the root |

## If you are running the evidence program

| Question | Read |
|---|---|
| Where does a real-world case come from? | [EVALUATION_PROTOCOL.md](EVALUATION_PROTOCOL.md) |
| What is the five-stage program? | [specs/validation-program.md](specs/validation-program.md) |
| What decides LAUNCH, NARROW or REFUSED? | [specs/launch-benchmark.md](specs/launch-benchmark.md) and [launch-decision.md](launch-decision.md) |
| How do I submit a task or a false positive? | `.github/ISSUE_TEMPLATE/` -- the forms carry the fields the corpus needs |
| What is in the external evidence kit? | [EVIDENCE_KIT.md](EVIDENCE_KIT.md) |

## Launch material

[launch-post.md](launch-post.md) is the long-form post, [launch.md](launch.md) the
sequence, [launch-sequence.md](launch-sequence.md) the order and the gates,
[social-preview.md](social-preview.md) the card. These describe how the project
presents itself; the numbers in them come from the pages above and are checked
against the same artifacts by `tests/test_launch_docs.py`.

## Release notes

[releases/](releases/) -- one file per release. `0.5.1` is current.

## A note on the numbers

Every measured number in this directory is produced by a command in the
repository, and the guards in `tests/` fail when a page drifts from the artifact
it quotes. If a number here disagrees with the artifact, the artifact is right
and the page is a bug.
