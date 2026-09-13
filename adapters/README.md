# Running greenwash outside Claude Code

greenwash is not tied to one host. The core is a CLI over a git diff plus an
optional test run; anything that can run Python can run it.

## Hosts, and how much of the mechanism each one gets

One ruleset, generated into every host's file by
[`sync_instructions.py`](./sync_instructions.py) so the copies cannot drift:

| Host | File | Enforcement |
|---|---|---|
| Claude Code | `skills/greenwash/SKILL.md` + `hooks/hooks.json` | skill **and** Stop hook -- the turn cannot end on a flagged diff |
| Codex, Amp, Jules, Zed, Qoder, CodeWhale, ... | `AGENTS.md` | rules only |
| Cursor | `.cursor/rules/greenwash.mdc` | rules only |
| GitHub Copilot | `.github/copilot-instructions.md` | rules only |
| Cline | `.clinerules/greenwash.md` | rules only |
| Windsurf | `.windsurf/rules/greenwash.md` | rules only |
| Gemini CLI / Antigravity | `GEMINI.md` | rules only |

"Rules only" means the agent is asked to run the check and paste the receipt --
it can still skip that under pressure, which is exactly why the Claude Code
Stop hook exists, and why pre-commit / the GitHub Action are the enforcement
everywhere else. Copy the file for your host into your project, and point
`GREENWASH` at this checkout (or replace it with the absolute path).

## As a Claude Code plugin (the mechanism layer)

```
claude --plugin-dir /path/to/greenwash
```

This is the only mode where the **Stop hook** runs automatically, blocking the
agent from ending its turn on a faked "done". Everywhere else, greenwash is a
check *you* run.

To add the behavioral layer to the hook, set:

```bash
export GREENWASH_TEST_CMD="python -m pytest -q"      # the project's tests
export GREENWASH_HELDOUT="tests/heldout"             # a suite the agent never saw
```

## As a pre-commit hook

`.pre-commit-hooks.yaml` is included. Point pre-commit at this repo (or copy
the hook locally) and add:

```yaml
repos:
  - repo: https://github.com/0DukePan/greenwash
    rev: v0.3.0
    hooks:
      - id: greenwash
```

It runs `scan --staged`, so it sees exactly what's about to be committed.

## As a GitHub Action

`action.yml` is a composite action:

```yaml
- uses: 0DukePan/greenwash@v0.3.0
  with:
    base: ${{ github.event.pull_request.base.sha }}
    run-tests: "pytest -q"
    heldout: "tests/heldout"
```

## As plain CI

```bash
BASE=origin/main RUN_TESTS="pytest -q" HELDOUT=tests/heldout bash adapters/ci.sh
```

Non-zero exit on any flag, so it drops into any pipeline.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | clean |
| 1 | one or more flags raised |
| 2 | tool error (not a git repo, git missing, ...) |
