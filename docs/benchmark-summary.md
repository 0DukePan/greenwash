# greenwash in one page

Every number here is produced by a command in this repository. Nothing on this
page is a projection, an estimate, or a target.

## 1. Does it catch a faked pass? Measured, no model in the loop.

28 tasks across six languages; 24 scored on the machine that ran this (Go, Rust,
Ruby and Java are not installed there and are recorded as `skipped: no
toolchain`, named in the artifact and kept out of every rate below). Each task
ships a buggy baseline, an honest fix and a scripted cheat, and every cheat was
verified to make the visible suite go green before it was scored.

| | Result |
|---|---|
| Planted cheats caught | **24 / 24** |
| -- by the static layer alone | 24 / 24 |
| -- by the behavioral layer alone | 22 / 24 |
| Missed by both layers | 0 |
| Honest fixes flagged | 0 / 24 |
| Buggy baselines flagged | 0 / 24 |
| Runtime | 172s for 24 scored tasks x 3 variants |

Raw: [`benchmark/results/detection.json`](../benchmark/results/detection.json),
run with `python benchmark/detection.py`.

## 2. Does it change what an agent does? Measured. It did not.

The claim under the detector numbers is that catching a fake pass changes agent
behaviour. On this corpus it did not:

| State | Silent cheats | Runs | Rate | 95% CI |
|---|---:|---:|---:|---|
| `off` | 5 | 72 | 7% | [3, 15] |
| `skill-only` | 5 | 72 | 7% | [3, 15] |
| `full` | 6 | 72 | 8% | [4, 17] |

**Delta (off -> full): -1.4 points -- no measurable effect at this sample size.**
Every arm's interval overlaps every other arm's. This is published as the null
it is, not as a reduction.

Raw: 252 rows in
[`benchmark/results/delta.jsonl`](../benchmark/results/delta.jsonl), summarised
by `python benchmark/report.py` into
[`benchmark/RESULTS.md`](../benchmark/RESULTS.md) and
[`benchmark/results/agent-delta.json`](../benchmark/results/agent-delta.json).

Two limits on this table, both load-bearing: the corpus is **first-party** (the
same people who wrote the detector wrote the tasks, so it measures the detector
against its own idea of a cheat), and the run **predates** the test-integrity
check, so it measures the plugin as it was then rather than as it is now. The
preregistered study that replaces it is
[EVALUATION_PROTOCOL.md](./EVALUATION_PROTOCOL.md).

## 3. Does it fire on honest work? Two measurements, both in the repository.

**On the corpus:** 0 false positives on 24 recorded honest fixes, and 0 flags on
200 genuinely-good live agent runs across the three arms above.

**On real history:** `python benchmark/fp_survey.py` re-runs the scanner over
the recent commits of three unrelated repositories -- 59 commits, 1,225 file
changes -- and produced:

| | Flags |
|---|---:|
| Total | 29 |
| The rules that always ask for an explanation | 20 |
| Genuine false positives | 9 |

The survey publishes its flags for inspection, not a rate: classifying 29 flags
by hand gives a number, not a population estimate, and calling it a rate would
overstate what was measured. The classes are written up in
[false-positives.md](./false-positives.md) and each fixed one became a
regression test. Raw:
[`benchmark/results/fp-survey.json`](../benchmark/results/fp-survey.json).

## What this page does not establish

- That greenwash reduces reward hacking in general. Nothing here was measured
  outside the corpus described above, and the corpus is first-party.
- That a clean report means the work is correct. It means the checks that ran
  did not find a problem -- the tool's own confidence level says how much that
  is worth, and with no behavioral check it says `LOW` on purpose.
- That the rate is stable. 100% recall on 24 tasks has a 95% interval of
  86.2-100%, and 0% false positives has an upper bound of 13.8% at that sample
  size. The intervals are the honest part of the table.

## Reproduce all of it

```bash
python benchmark/detection.py            # section 1
python benchmark/report.py --out benchmark/RESULTS.md   # section 2's tables
python benchmark/fp_survey.py --limit 40 # section 3
python benchmark/polyglot.py             # the 15 language cases, 15/15
```

The generated tables live in [`BENCHMARK.md`](../BENCHMARK.md); the prose around
them in this file is checked against the artifacts by
`tests/test_launch_docs.py`, so a number that moves breaks CI rather than
drifting.
