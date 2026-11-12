# Running greenwash outside Claude Code

greenwash is not tied to one host. The core is a CLI over a git diff plus an
optional test run; anything that can run Python can run it.

## Hosts, and how much of the mechanism each one gets

One ruleset, generated into every host's file by
[`sync_instructions.py`](./sync_instructions.py) so the copies cannot drift:

| Host | File | Enforcement |
|---|---|---|
| Claude Code | `skills/greenwash/SKILL.md` + `hooks/hooks.json` | skill **and** Stop hook -- the turn cannot end on a flagged diff |
| Codex | `codex/` plugin, `AGENTS.md` | Stop hook (strict by default) **and** rules |
| Cursor | `.cursor/rules/greenwash.mdc` | rules only |
| Windsurf | `.windsurf/rules/greenwash.md` | rules only |
| Cline | `.clinerules/greenwash.md` | rules only |
| GitHub Copilot | `.github/copilot-instructions.md` | rules only |
| Gemini CLI / Antigravity | `GEMINI.md` | rules only |
| Amp, Jules, Zed, Qoder, CodeWhale, ... | `AGENTS.md` | rules only |

## The honest split

Two hosts can *coerce* the agent: Claude Code and Codex expose a Stop hook, so
the check runs whether or not the model cooperates. Everything else gets rules,
and a rule is a request -- a model under pressure can skip it, which is exactly
the behaviour this tool exists to catch. Do not read the Cursor or Windsurf file
as enforcement.

If you use Cursor or Windsurf, the enforcement is one of these, and both live
outside the chat:

```bash
greenwash init                 # write .greenwash/config.json
greenwash waive --help         # the auditable way to resolve a finding
```

- **pre-commit** — `repos: [{repo: https://github.com/0DukePan/greenwash, rev: v0.4.2}]`
  runs the checker on every commit, before it reaches a branch.
- **The GitHub Action** — `.github/workflows/greenwash-report-only.yml` in this
  repository is a working example: report-only, read-only permissions, no
  secrets, the report uploaded as an artifact. Delete `continue-on-error` and
  add `--fail-on suspicious` when you want it to block.

Neither needs the agent's cooperation, which is the point.

Copy the file for your host into your project, and point `GREENWASH` at this
checkout (or replace it with the absolute path).

## Which rules each host receives

Every rules file is generated from the same source, so the wording is identical
across Cursor, Windsurf, Cline, Copilot and `AGENTS.md`. What differs is the
shape the host reads: `.mdc` with front matter for Cursor, `.md` elsewhere. If
you change one, run `python adapters/sync_instructions.py` and commit the
result -- `tests/test_manifests.py` fails if they drift.

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

The hook runs the behavioral layer by default: it discovers the project's test
command, runs it, and compares against the committed baseline. Pin the command
or add a held-out suite when you want more than discovery:

```bash
export GREENWASH_TEST_CMD="python -m pytest -q"      # pin the command
export GREENWASH_HELDOUT="tests/heldout"             # a suite the agent never saw
```

`hooks/hooks.json` runs `python3` and falls back to `python`, since neither name
exists on every platform; `tests/test_hook_command.py` executes the real command
through the platform shell so a hook that cannot start fails CI on both.

## As a pre-commit hook

`.pre-commit-hooks.yaml` is included. Point pre-commit at this repo (or copy
the hook locally) and add:

```yaml
repos:
  - repo: https://github.com/0DukePan/greenwash
    rev: v0.4.2
    hooks:
      - id: greenwash
```

It runs `scan --staged`, so it sees exactly what's about to be committed.

## As a GitHub Action

`action.yml` is a composite action:

```yaml
- uses: 0DukePan/greenwash@v0.4.2
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
