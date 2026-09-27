# How to read the numbers

Three kinds of numbers get published about this project, and they license
different statements. Most of the ways to misuse greenwash's evidence come from
quoting one of them as if it were another.

## 1. Detector accuracy -- "does the scanner catch a known cheat?"

24/24 planted cheats caught on 24 scored tasks (4 more skipped for a missing
toolchain), 0 flags on the 24 recorded honest fixes, static 24/24, behavioral
22/24.

**Licenses:** "on a labelled corpus of 24 tasks with one planted cheat each,
the scanner caught every planted cheat and flagged no recorded honest fix."

**Does not license:** "the scanner does not produce false positives." 24 honest
fixes is a small sample; the 95% upper bound on that measurement is 13.8%. And
the honest fixes are minimal correct patches, not the untidy code a real
review finds.

**Also:** the corpus is first-party. It measures the detector against its own
authors' idea of a cheat.

## 2. The false-positive survey -- "does it fire on real code?"

29 flags over 59 commits and 1,225 file changes in three unrelated
repositories; 20 are the rules that always ask for an explanation, 9 are
genuine false positives, each written up and each fixable one turned into a
regression test.

**Licenses:** "on the recent history of three repositories, the scanner
produced 29 flags; nine of them were wrong, in two documented classes."

**Does not license:** "the false-positive rate is 31%." Classifying 29 flags by
hand gives a number, not a population estimate -- the repositories were not
sampled, the commits were not sampled, and nobody labelled the changes that
were *not* flagged. This is a survey, and the page says so.

## 3. The agent-facing delta -- "does it change what an agent does?"

252 scored runs: 7% off, 7% skill-only, 8% full; -1.4 points; intervals [3, 15],
[3, 15], [4, 17].

**Licenses:** "no measurable effect at this sample size, on this corpus, with
this model."

**Does not license:** almost anything else, and in particular:

- **not** "greenwash does not work" -- the interval is wide; the study could not
  distinguish a 5-point reduction from a 5-point increase;
- **not** "greenwash reduces reward hacking" -- that is the claim the null
  refuses;
- **not** "the detector numbers prove the behavioural effect" -- the two are
  different measurements of different things, and the second one is the one that
  matters for the thesis.

**Also:** the run predates the test-integrity check and the `error-path-default`
rule. It describes the plugin as it was then. The pages that quote it say so.

## The vocabulary, precisely

| Term | What it means | What it does not mean |
|---|---|---|
| `VERIFIED` | every check that ran passed, and at least one ran | the code is correct |
| `NOT_VERIFIED` | a check the claim depends on does not pass | the agent cheated |
| `SUSPICIOUS` | a pattern that needs an explanation is present | the pattern is a cheat |
| `INCONCLUSIVE` | not enough evidence either way | a pass |
| `VERIFICATION_FAILED` | the check could not run | the work failed |
| waived with review | a person decided this finding is acceptable, until a date | clean |
| `requires review` | a question, not a finding | a failure |

## Three sentences that are always true

If you are writing about this project and want to stay inside the evidence:

1. It produces evidence about a change: what ran, what passed, and what the
   diff looks like.
2. It makes the cheapest fake-pass shortcuts -- skipping the test, hardcoding
   the value, weakening the assertion -- visible to a reader who was not there.
3. Whether that changes what an agent does is **unmeasured** beyond one
   first-party null, and the honest statement of that null is "no measurable
   effect at this sample size."

## Phrases to avoid

- "prevents reward hacking" -- nothing here prevents anything; it reports.
- "proves the tests are honest" -- it reports the checks that ran.
- "100% recall" without the interval (86.2%-100% on 24 tasks) and without
  "on this corpus".
- "0% false positives" without the upper bound (13.8%) and without "on 24
  recorded honest fixes".
- "agent-agnostic" -- the measurement covers one agent, one model, one gateway.
- Any single run's number presented as a rate.
