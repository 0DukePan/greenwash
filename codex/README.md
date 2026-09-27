# The Codex plugin: a strict stop gate

This directory is the Codex packaging of greenwash. It is the same checker, the
same rules and the same exit codes as the Claude Code plugin -- what differs is
the profile and the hook contract.

| File | What it is |
|---|---|
| `plugin.json`, `.codex-plugin/plugin.json` | the manifest, in both spellings |
| `hooks/codex-hooks.json` | the Stop hook: POSIX command, plus a Windows command |
| `scripts/greenwash_hook.py` | the hook itself -- runs `greenwash --strict`, prints findings, exits 2 to block |
| `skills/greenwash/SKILL.md` | what the agent reads |

## Install

```bash
pipx install greenwash-cli
```

Then point Codex at this directory as a plugin. The hook resolves its own
location, so the only hard requirement is that Python 3.10+ (with the
`greenwash-cli` package) is on `PATH`:

```bash
python codex/scripts/greenwash_hook.py < payload.json
```

## The trust boundary, stated honestly

- **Strict is the default here, and it is not the CLI default.** `greenwash` on
  the command line reports and exits 0. A plugin is opted into once, by someone
  who wants a gate, so the plugin profile runs the longer table.
- **A trusted plugin Stop hook is a real workflow gate, not an
  enterprise-admin-only enforcement boundary.** It stops an agent that is
  cooperating with the host. An agent that edits the hook, runs `git commit
  --no-verify`, or works outside the host is not stopped by it -- that is what
  branch protection and CODEOWNERS are for, and no local tool can substitute
  for them.
- **A broken checker never blocks a developer, and never claims a pass.** If
  the CLI cannot run, the hook prints `could not verify this turn` and exits 0.
  That is a decision, not an oversight: a verification tool that bricks your
  editor when Python is missing is a tool people uninstall. The uncertainty is
  printed into the transcript, so the turn is visibly unchecked rather than
  silently clean.
- **The plugin root is resolved defensively.** `PLUGIN_ROOT` first,
  `CODEX_PLUGIN_ROOT` and `CLAUDE_PLUGIN_ROOT` as compatibility spellings, and
  the hook's own location as the last resort -- so a host that substitutes a
  token this file does not know about still starts the hook.

## What it prints

Verdict, the checks that ran, the blocked reasons, the waiver status, and one
actionable next step. Verbatim, on a repo where the agent hardcoded the value
its test asserts:

```
greenwash (strict): BLOCKED -- SUSPICIOUS (low confidence)
checks: visible tests: 1/1; integrity: pass
blocked: the diff contains a pattern that needs an explanation: [hardcoded-return] src/calc.py:2
waivers: 0 active, 0 lapsed
  [hardcoded-return] src/calc.py returns literal 5 (directly), which a test asserts against
next: fix the finding, or record a decision with `greenwash waive --rule <rule> --path <file> --reason <why> --reviewer @you --expires <date>` and stop again.
```

Reproduce that block with `python demo/codex_strict.py`, which drives this hook
the way the host does -- payload on stdin, exit code read, not a transcript.

## Certification

The `strict-hooks` CI job runs the clean / block / waive / error flows for both
this hook and the Claude one against the same fixture repo, and asserts they
reach the same verdict for the same input. If they ever disagree, that is a bug
in one of them, not a difference in policy.
