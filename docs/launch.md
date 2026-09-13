# Launch notes

Draft material for posting greenwash publicly. The one rule: **lead with the
measured number, not the idea.** If the number isn't in yet, don't post the
"it works" framing — post the "here's how to measure it" framing instead.

## The 3-sentence pitch

1. Coding agents under pressure to show green sometimes make the suite green
   instead of fixing the code — skip the test, mock the thing under test,
   hardcode the expected value, swallow the exception.
2. greenwash runs a check that the agent cannot skip: a `Stop` hook that fires
   on every turn end, static analysis plus an actual test run against the
   committed baseline.
3. Measured: silent-cheat rate went from **X%** (no plugin) to **Y%** (skill +
   hook), false-positive rate **Z%** — n=NN across NN tasks. *(`X/Y/Z` filled
   in from `benchmark/RESULTS.md`.)*

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
- Cite the paper as motivation, not as proof that greenwash works:
  <https://arxiv.org/abs/2511.18397>.

## Checklist

- [ ] `benchmark/RESULTS.md` exists and is committed
- [ ] README headline replaced with the real delta
- [ ] demo recorded and linked
- [ ] release tagged (`claude plugin tag .`)
