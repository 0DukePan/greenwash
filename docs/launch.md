# Launch notes

Draft material for posting greenwash publicly. The one rule: **lead with the
measured number, not the idea.** If the number isn't in yet, don't post the
"it works" framing — post the "here's how to measure it" framing instead.

The kit these notes grew into lives in `docs/`:

| Piece | Where |
|---|---|
| The sequence, the scorecard and the standing assessment | [launch-sequence.md](./launch-sequence.md) |
| One page of measured numbers, with the raw artifacts linked | [benchmark-summary.md](./benchmark-summary.md) |
| What did not work, with the numbers attached | [what-did-not-work.md](./what-did-not-work.md) |
| Report mode versus strict mode | [report-vs-strict.md](./report-vs-strict.md) |
| Adoption guide | [ADOPTION_GUIDE.md](./ADOPTION_GUIDE.md) |
| Waiver policy | [WAIVER_POLICY.md](./WAIVER_POLICY.md) |
| Preregistration for the independent study | [EVALUATION_PROTOCOL.md](./EVALUATION_PROTOCOL.md) |
| How to read the numbers (and what they do not license) | [RESULT_INTERPRETATION.md](./RESULT_INTERPRETATION.md) |
| GitHub release post | [releases/0.4.2.md](./releases/0.4.2.md) |
| Long-form technical post | [launch-post.md](./launch-post.md) |
| Social preview, verified | [social-preview.md](./social-preview.md) |

Two demos back the posts with captured output rather than transcription:
`python demo/strict_claude.py --terse` and `python demo/strict_codex.py --terse`.

## The 3-sentence pitch

1. Coding agents under pressure to show green sometimes make the suite green
   instead of fixing the code — skip the test, mock the thing under test,
   hardcode the expected value, swallow the exception.
2. greenwash runs a check that the agent cannot skip: a `Stop` hook that fires
   on every turn end, static analysis plus an actual test run against the
   committed baseline.
3. Measured: the base rate is **7%** silent cheating without the plugin (95% CI
   [3, 15]) — 5 of 72 runs over 24 tasks, three runs each — and **8%** with the
   skill and hook ([4, 17]): a null, inside the noise. False positives **0%**
   across 200 genuinely-good runs. Lead with the base rate and the misses, not
   with a reduction; there isn't one to claim. *(Artifacts:
   `benchmark/RESULTS.md`, 252 rows in `benchmark/results/delta.jsonl`.)*

## Demo

Use `assets/demo.gif` -- the loop at the top of the README (agent says "done",
the hook blocks the stop), built by `assets/make_demo_gif.py`. Post it inline.

## Show the honest limits up front

- It is a smell detector, not a prover; it can be routed around by design.
- The behavioral layer (`verify`) is the durable signal; the static layer is a
  fast pre-filter.
- Python is the strongest language; the rest are regex packs.
- It reports its own false-positive rate — say the number.

Owning the limits is what stops the "just grep lol" comment from landing.

## Where the framing can go wrong

- Don't claim it "prevents" reward hacking. It makes the cheapest cheats
  expensive and forces an explanation. Say that.
- Don't post the number from a single task or a single run. The report prints a
  confidence interval for a reason.
- **The first measured delta is a null, and that gets said first.** The tool
  moved nothing on this corpus; what it did do is measure the base rate (7%) and
  show where it has no leverage (a swallowed exception the visible suite does
  not notice, with no held-out suite to disagree). Publishing a null is the
  credibility move; hiding it is the one that gets caught.
- Cite the paper as motivation, not as proof that greenwash works:
  <https://arxiv.org/abs/2511.18397>.

## Checklist

- [x] `benchmark/RESULTS.md` exists and is committed (252 rows behind it)
- [x] README states the delivered numbers -- detector accuracy in the headline
      and the agent-facing null immediately beneath it, with its intervals under
      "Numbers". No headline delta: there is no effect to claim, and the page
      now says so above the fold rather than only in a subsection.
- [x] demo recorded and linked
- [x] release tagged (`claude plugin tag .` -> `greenwash--v0.4.0`)
