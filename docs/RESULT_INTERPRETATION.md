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

The scanner was run twice over 250 commits and 1,029 file changes in ten
unrelated repositories. Run 1: 109 flags, 104 of them one rule
(`verifier-config-changed`) firing on CI and dependency configuration. Run 2,
after that rule was narrowed to fire only when a change can alter what runs: 14
flags -- 12 from the rules that ask rather than accuse, and 2 accusatory flags
that were both rejected by hand. Two of the asking flags are `error-path-default`
(the rule that had never been measured), seen through one commit and its merge.

**Licenses:** "on the recent history of ten repositories the scanner produced 14
flags, 12 of them from the rules that ask rather than accuse; of the two that
accused, both were rejected by hand. The one rule that produced 104 of the
first run's 109 flags produces 7 now, and all seven are real runner changes."

**Does not license:** "the false-positive rate is 14%." Classifying 14 flags by
hand gives a number, not a population estimate -- the repositories were not
sampled, the commits were not sampled, and nobody labelled the changes that
were *not* flagged. This is a survey, and the page says so. It also does not
license "the rule is precise": a narrowed rule sees less, and the taxonomy keeps
`runner-config-tamper` at `PARTIAL` for exactly that reason.

## 3. The agent-facing delta -- "does it change what an agent does?"

252 scored runs: 0% integrity cheats in every arm (0/72 each); +0.0 points;
intervals [0, 5], [0, 5], [0, 5]. The 16 runs the v1 labels counted as cheats
are corrected to `underspecified`: honest fixes to tasks whose hidden tests
checked unstated requirements.

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

**And one more, added after the fact:** the instrument that produced these
labels could not record a cheat that passes the held-out suite, the rows carry
no diffs or detector flags, and the run has not been repeated since the fix. A
0% therefore means "this instrument found nothing", not "there was nothing to
find". See sections 1 and 12 of [what-did-not-work.md](./what-did-not-work.md).

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
