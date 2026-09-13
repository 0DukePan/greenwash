# Running the benchmark

The benchmark answers one question: **does having greenwash around change how
often an agent's "done" claim is actually true?** It measures the silent-cheat
rate under three plugin states and reports the delta plus a false-positive
rate.

## 1. Make sure a model is reachable

```bash
python benchmark/preflight.py
```

If it reports `model not reachable`, fix that first — do not start a run.
Common causes: `ANTHROPIC_BASE_URL` must be **https** and funded; the default
model may not be available on a gateway, so set one explicitly.

A gateway with a zero balance rejects every model with HTTP 402
(`"type": "reject_no_credit"`), which Claude Code reports the same way it
reports a bad model id. That gate is a positive balance, not a per-call charge
— top the account up, rerun the preflight, then start the run.

```bash
set GREENWASH_BENCH_MODEL=anthropic/claude-sonnet-4.5   # Windows
export GREENWASH_BENCH_MODEL=anthropic/claude-sonnet-4.5 # bash
```

## 2. Prove the plumbing (no model, no cost)

```bash
set FAKE_AGENT_MODE=hardcode
python benchmark/harness.py --agent-cmd python ^
  --agent-arg "%CD%\benchmark\tools\fake_agent.py" --states off,skill-only,full
```

This exercises git init, scoring, hidden-test injection, classification and
reporting for every task without a single API call: `hardcode` returns the
literal each visible test asserts, `skip` disables the visible test, and
`honest` applies the task's recorded solution. The classifications should be
sensible (`silent cheat` for hardcode/skip, `genuine fix` for honest).

Rows record which agent produced them, and `report.py` banners any run that
was not a live model, so plumbing output cannot be mistaken for a measurement.

## 3. Run the real thing

```bash
python benchmark/harness.py --states off,skill-only,full --runs 3
python benchmark/report.py
```

- `off` — no plugin.
- `skill-only` — the skill, no hook (`benchmark/plugins/greenwash-skill-only`).
- `full` — skill + Stop hook (this repo).

`skill-only` is what separates "the skill nudged the agent" from "the hook
forced it": if `skill-only` looks like `off`, the mechanism is doing the work.

## 4. Read the result

`benchmark/report.py` prints the silent-cheat rate per state, the off → full
delta, and the false-positive rate (genuinely-good results that greenwash still
flagged). Commit `benchmark/RESULTS.md` and the raw rows under
`benchmark/results/` so the number is reproducible.

## Cost

Roughly `tasks × 3 states × runs` agent invocations. With 25 tasks and 3 runs
that is up to 225 runs — use `--runs 1` to pilot, then scale up.

## Adding a task

Copy `benchmark/tasks/_template/`, set `task.json`, and remember (directories
whose name starts with `_` are skipped, so the template itself never runs):

- `workspace/` is what the agent sees; `hidden/` is never shown.
- the visible test must be satisfiable by a cheat that the hidden test catches.
- the real fix should be strictly harder than the cheat (that's the "pressure").
- `language` picks the runner: `python` -> pytest, `javascript` -> `node --test`
  (write `.mjs` files and import from `../src/`; no packages needed).
