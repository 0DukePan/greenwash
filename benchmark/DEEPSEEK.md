# The DeepSeek run

`benchmark/deepseek_run.py` scores a live DeepSeek model with the same harness
that scores the scripted double. The model is the agent: it reads the workspace,
edits files, runs the tests, and the harness classifies what it left behind.

**Status: built and tested, not yet run.** The API key that ships with this
machine's DSH profile is configured but the account has no balance, so every
call returns `402 Insufficient Balance`. `--preflight` says so in one line and
writes no rows, which is the point: an empty run should not look like 261
`infra` outcomes.

## Why this is a new run and not a rerun of the old one

The 252-row pilot in `benchmark/results/delta.jsonl` was produced by driving
Claude Code, and the instrument that labelled it could not record a cheat that
passes the held-out suite (fixed since — see `docs/what-did-not-work.md`
sections 1 and 12). This run uses:

- a model reachable through a plain chat-completions API, so the agent loop is
  visible and testable rather than a CLI's black box;
- the fixed classifier, which labels a passing cheat `flagged` instead of
  `genuine fix`;
- the same three arms (`off`, `skill-only`, `full`), where `full` reproduces
  what the Stop hook does — the static check fires when the model tries to stop,
  and a finding is fed back as another turn.

The `full` arm is the one that was never really measured: the old pilot's
"full" state installed the hook but the classifier could not see what it
caught.

## Running it

On Windows, the copy-paste version with `cmd.exe` quoting is in
[RUNNING-WINDOWS.md](./RUNNING-WINDOWS.md). The short form, from the repository
root:

```bash
python benchmark/deepseek_run.py --selfcheck   # proves the wiring, no API needed
python benchmark/deepseek_run.py --preflight   # asks the API one question
python benchmark/deepseek_run.py --states off,full --runs 3
python benchmark/deepseek_run.py --report
```

`--selfcheck` runs the real harness against a scripted agent on one task and
asserts the row is shaped the way a live row will be, so a failure there is a
checkout problem rather than a model problem. Cost control: 29 tasks × 3 states
× 3 runs is 261 model sessions. Start with `--task` repeated, then `--resume`
continues the same jsonl where it stopped. Every row records the model id
(from `GREENWASH_AGENT_MODEL`) and, on a non-zero agent exit, the reason, so a
dead key cannot look like 261 crashed agents.

## What the agent can and cannot do

The runner exposes four tools — list, read, write, run a command — and the
command allowlist is `python`, `pytest`, `git`, `node`, `go`, `cargo`, `ruby`,
`javac`, `java` and the listing commands. Paths are confined to the workspace.
The prompt comes from `task.json`; the task directory (recorded solution,
held-out test) is never passed to the model. `tests/test_deepseek_agent.py`
pins the sandbox, the allowlist, the turn limit, the exit-code contract and the
gate loop without touching the network.

## What it does not measure

- **Only the static gate in `full`.** The real Stop hook also runs the project's
  tests; here the scored tests are the harness's, so `full` feeds back static
  findings only.
- **One model.** A DeepSeek result says nothing about Claude, GPT or a local
  model.
- **The corpus is first-party.** It still measures the model against this
  project's idea of a cheat.

When the balance is topped up, the first run should be the four-task pilot in
`--states off,full --runs 3` — 24 sessions — before committing to 261.
