# The benchmark a reader can run

```bash
git clone https://github.com/0DukePan/greenwash && cd greenwash
python benchmark/verify.py          # 90 seconds, no model, no network
python benchmark/verify.py --quick  # 10 seconds, skips the task corpus
```

No API key, no account, no clone of anything but this repository. It exits
non-zero on the first measurement that regresses, so it is also the acceptance
test for a change.

## What it runs

| Measurement | What it puts in front of the checker | Time |
|---|---|---|
| `detection.py` | 28 tasks in six languages, each with a buggy baseline, a recorded honest fix and a scripted cheat, scored by the scanner and the language's real test runner | ~50 s |
| `tampering.py` | 11 attacks, each beside a legitimate lookalike that must stay quiet | ~45 s |
| `polyglot.py` | a positive and a negative case per language pack | <1 s |

The task corpus is the slow one because every variant runs the real suite in a
subprocess; it is parallelised across tasks, which took it from 172 s to 48 s on
the machine that wrote this.

## What the numbers are

From the committed artifact on a Windows laptop with Python, Node and Java
installed, and no Go, Rust or Ruby -- the three missing toolchains are recorded
as `skipped: no toolchain` and kept out of every rate:

| | Result |
|---|---|
| Planted cheats caught | 25 of 25 |
| -- static layer alone | 24 of 25 |
| -- behavioural layer alone | 23 of 25 |
| Missed by both | 0 |
| Honest fixes flagged | 0 of 25 |
| Buggy baselines flagged | 0 of 25 |

Your checkout will differ: with Go, Rust and Ruby installed it scores all 28.
The artifact names every skipped task rather than quietly scoring what it has.

## What it does not measure

- **Whether a model cheats.** That needs `harness.py` and a reachable model;
  `deepseek_run.py` is the runner for it, and the eight-task pilot in
  [DEEPSEEK-PILOT.md](../benchmark/DEEPSEEK-PILOT.md) is what that looks like.
- **Whether greenwash changes model behaviour.** Different question, needs the
  `full` arm, and it has not been measured on a current model.
- **A false-positive rate.** The corpus's honest fixes are 25, not a sample of
  real code; the real-history survey is
  [false-positive-survey.md](./false-positive-survey.md) and it is a survey, not
  a rate.
- **Correctness.** A passing suite is not proof, and neither is this. The
  verdict vocabulary says evidence, never proof; the open gaps are in
  [what-did-not-work.md](./what-did-not-work.md).

## Why this exists

The previous benchmark required a funded model, a pinned corpus and this
project's own machinery to produce a number -- which meant nobody outside
could check it. This one is three subprocesses and a JSON file.

If you run it and get a different answer, that is a bug report worth filing:
the corpus is in `benchmark/tasks/`, each task is a directory with a
`task.json`, and adding one needs no code.
