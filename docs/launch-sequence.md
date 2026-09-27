# Launch sequence, scorecard and standing

This file is the plan-of-record for putting greenwash in front of people, and
the place where its targets are measured against what actually happened. It
exists so that a missed target produces a published gap and better onboarding,
rather than a broader claim.

Two rules govern everything below:

1. **Publish the evidence that would disprove the marketing claim.** A null or
   negative result is a result to publish, not one to bury.
2. **When a target is missed, say so in this file** -- with the measured number,
   not the target restated.

## The sequence

| # | Step | Status in this repository | What it still needs |
|---|---|---|---|
| 1 | Verified 0.4.2 integrity release | **Prepared.** Version agrees across `pyproject.toml`, `greenwash/__init__.py`, both plugin manifests and the npm package -- asserted by a test. `CHANGELOG.md` has the 0.4.2 section. Release notes are written (`docs/releases/0.4.2.md`). | The tag and the push. Also: the release checklist's clean-environment smoke runs (wheel install, npm pack, Action and pre-commit fixtures), which CI performs but whose output belongs in the release evidence. |
| 2 | Tested Codex strict-gate release | **Prepared and certified in-repo.** The plugin exists; `tests/test_codex_plugin.py` validates both manifests, both command spellings, and the clean / block / waive / error flows; `tests/test_strict.py` runs the same four flows through the Claude hook and asserts they reach the same verdict; the `strict-hooks` CI job runs both. | The same tag as step 1, and a maintainer's first real Codex session. |
| 3 | Independent evaluation governance and recruitment | **Drafted.** `docs/EVALUATION_PROTOCOL.md` specifies corpus authorship, merge authority, the acceptance contract and the anti-contamination protocol. The issue forms for a task proposal and a design-partner application exist. | Creating the separate evaluation repository, recruiting at least three non-core maintainers with merge authority, and six task authors. Core maintainers must not author tasks. |
| 4 | Design partners before broad behavioural claims | **Held as a constraint, not a step.** No page in this repository claims a behavioural effect: the README leads with the null, and `docs/RESULT_INTERPRETATION.md` lists the phrases that overstate it. | Ten partners, and pilots recorded against the seven fields in the design-partner form. |
| 5 | Preregistration and sealed corpus hash published | **Draft only.** The protocol is written; the fields marked *to be frozen* are empty, because freezing them before the corpus exists would be theatre. | The corpus, its hashes, the detector commit, the image digest, the seed -- frozen and published **before** the first live run. |
| 6 | Run and publish the 900-run study | **Not started.** No run has been executed, and nothing in this repository's numbers comes from it. | Compute, credentials, the pinned image, and the corpus from step 5. Result published whatever it says. |
| 7 | Technical launch post with evidence and limits first | **Written** (`docs/launch-post.md`). It opens with the null, then the detector numbers, then the design, then "what I got wrong". | Publication. |
| 8 | Share: GitHub Release, technical communities, direct maintainer outreach | **Not started.** | A maintainer with accounts on those surfaces. Outreach is per-maintainer, not a broadcast. |
| 9 | Weekly progress with real numbers | **Template below.** | Real numbers, every week, including the weeks they are embarrassing. |

## Weekly scorecard

Targets, and the place where the measured value goes. The **Measured** column is
filled in weekly from GitHub Insights and the contributor ledger -- never from
memory, and never left as a target once the week is over.

| Metric | Week 1-2 | Week 3-6 | Week 7-10 | Week 11-13 | Measured |
|---|---:|---:|---:|---:|---|
| Stars | 25 | 100 | 250 | 500 | *not yet published* |
| Forks | 2 | 8 | 15 | 25 | *not yet published* |
| Partners | 2 | 5 | 8 | 10 | *0* |
| Documented pilots | 0 | 1 | 2 | 3 | *0* |
| External tasks | 10 | 30 | 60 | 60 frozen | *0* |
| Codex gate | planned | certified | maintained | maintained | *certified in CI; no real session yet* |
| Study runs | 0 | pilot | 900 complete | results public | *0* |

The star and fork rows are deliberately unmeasured here: this repository does not
query GitHub, and a number copied into a file by hand is a number that drifts. If
the scorecard is to be worth anything, those rows come from the Insights page on
the day of publication.

**The gap rule.** If a target is missed, the entry says the measured value and
the next action is either better onboarding, better documentation, or more
outreach. It is never a broader claim, a longer README, or a retargeted metric.
Rewriting the target after the fact would make this table a mirror instead of a
measurement.

## The final standard, assessed honestly

| # | Condition | Status |
|---|---|---|
| 1 | Public install commands install this project, not a namesake | **Met for Python** (`greenwash-cli`, and the README says why). **Withdrawn for npm**: the registry name is not owned here, so `npx greenwash` is no longer advertised and `npm/README.md` documents the local pack path instead. |
| 2 | GitHub Actions exercise every advertised integration | **Met.** One job per surface: the CLI matrix, the six-language corpus, the npm shim (pack, install, assert a forwarded exit code), the Action and the pre-commit hook against a planted fake pass, and both strict gates. |
| 3 | Claude and Codex both have tested strict stop-gate paths | **Met.** `tests/test_strict.py` runs clean / block / waive / error through both hooks and asserts the verdicts match; the `strict-hooks` CI job runs it on every push. |
| 4 | Suspicious findings require an auditable decision | **Met in strict mode.** A `requires_review` finding blocks until a waiver names a reviewer, a reason and an expiry; suppression is refused rather than honoured. In report mode they are questions, which is the intended default. |
| 5 | An independent group authored and reviewed the evaluation corpus | **Not met.** The corpus is first-party. This is the largest open item, and `docs/EVALUATION_PROTOCOL.md` is the invitation. |
| 6 | The outcome study is preregistered and published in full | **Half met.** The preregistration is drafted and published; the study has not been run. |
| 7 | Public claims match the result, including a null | **Met.** The null is on the front page, in the benchmark one-pager, in the launch post and in the release notes, with its intervals and its two limits. |
| 8 | Real maintainers have used the tool in real projects | **Not met.** Zero pilots recorded. |
| 9 | Growth comes from evidence and adoption rather than manipulation | **Held.** No paid stars, no fabricated testimonials, no fake accounts. The scorecard above is the audit trail. |
| 10 | The product remains local, deterministic, dependency-free and honest about what it cannot establish | **Met.** No network, no account, no model; zero runtime dependencies; `INCONCLUSIVE` and `VERIFICATION_FAILED` are distinct outcomes, and a report with no behavioral evidence is capped at `LOW` on purpose. |

Five met, three not met, one half met, one withdrawn-and-replaced. The
uncomfortable ones are 5, 6 and 8 -- and 8 is the one that decides whether any
of this was worth doing.
