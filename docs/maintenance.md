# Maintenance

What keeps this repository maintainable by one person, what the limits are, and
how the numbers below were measured. A change that breaks one of these is a
change to the maintenance contract, not a detail.

## The contract

| Rule | Target | How it is enforced |
|---|---|---|
| One branch, one worktree | `main` only, local equal to `origin/main` | deleted at the 0.4.2 cleanup; stale branches are exported to `archive/branches/` as bundles before deletion |
| A local loop measured in seconds | default `python -m pytest -q` ≤ 90 s | `addopts = -m "not slow"`; the default gate is 154 tests |
| A real gate on every push | product behaviour, ≤ 5 min wall | `-m "not program"` in the `product` CI job, with `pytest-xdist` |
| The whole suite, including Windows | nothing silently skipped | nightly `full` job: Ubuntu and Windows × 3.10 and 3.12 |
| The suite is idempotent | two runs in a row give the same answer | no wall-clock or shared-state fixtures; `tests/conftest.py` isolates the hook's block budget |
| One process home | GitHub Issues | no in-tree ticket files |
| Every published number is guarded | guards are in the default gate | README, claim ledger, survey and docs tests |

## The three commands

```bash
python -m pytest -q                    # ~10 s: pure units and the claim guards
python -m pytest -q -m "not program"   # the product's real gate: 2.5 min on four workers, 7 min serial
python -m pytest -q -o addopts=        # everything, including the frozen programme
```

## What the 0.4.2 cleanup changed

- **42 local branches → 1**, and four remote branches → one. The three branches
  that were not merged are preserved as bundles in [`../archive/branches/`](../archive/branches/README.md),
  with their tips and what they held.
- **8 worktrees → 1.**
- **12 minutes → 10 seconds** for the default test run. Tests that spawn a
  process carry the `slow` marker; the frozen research programme carries
  `program` and is excluded from the per-push gate.
- **Push CI no longer runs Windows.** It runs the 10-second smoke class on both
  supported Pythons, the product gate in parallel, and the language, npm,
  strict-gate and integration jobs. Windows and the whole suite moved to a
  nightly schedule. That is the deliberate cost of the 10-minute Windows jobs.
- **The suite is idempotent.** Two separate causes were found and fixed: the
  Stop hook's block budget was inherited from whichever ancestor repository a
  test's temp directory sat under (the suite passed once and failed the second
  time), and the waiver fixtures used an expiry exactly at the thirty-day
  ceiling, which fails just after local midnight when the timezone is ahead of
  UTC.
- **No in-tree tickets.** `.scratch/` is gone; work is tracked in GitHub Issues,
  and `CONTRIBUTING.md` says so.

## What is still not a 10

Two criteria are only partly met, and saying otherwise would be the thing this
project exists to catch:

1. **The tree's LOC ratio is unchanged.** `benchmark/` is still about 18k lines
   against 8k of product. The programme is *identified* (`benchmark/README.md`
   names the eight published-number scripts, the tests carry `program`), and it
   is out of the push gate — but it has not been physically separated, because
   moving fourteen modules and their imports buys legibility at the cost of a
   risky refactor. The honest statement is "the programme is frozen and marked",
   not "the repository is small".
2. **The docs were not consolidated.** Twenty-three pages under `docs/` plus
   seven at the root are still there; the process pages (launch sequencing,
   evaluation protocol, evidence kit, roadmaps) remain in place because tests
   reference several of them and moving them in the same pass as the test split
   would have mixed two risks. The next pass moves them under `docs/archive/`
   and teaches the claim ledger to skip that directory.

## The rule that keeps it honest

If a change makes the default gate slower than 90 seconds, puts Windows back on
the push path, or adds a test that depends on wall-clock time or shared state,
it needs a reason in the pull request. The numbers in this page are the reason
the rules exist; update them when they move, in the same change.
