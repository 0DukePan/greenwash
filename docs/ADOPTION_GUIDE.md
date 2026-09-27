# Adoption guide

How to put greenwash on a real repository without making anyone's day worse. It
is written for the person who has to answer "why is this thing blocking my
merge", so it leads with the cheap options and puts the gate last.

Nothing here needs an account, a network call, an API key, or a model. The tool
reads your diff and runs your tests.

## 1. Install (one minute)

```bash
pipx install greenwash-cli      # or: pip install greenwash-cli
cd your-repo
greenwash --version
```

Two naming facts worth knowing, because both have bitten people:

- The **distribution** is `greenwash-cli`; the **command** and the **import
  name** are `greenwash`. `pip install greenwash` installs an unrelated
  project.
- `npx greenwash` is **not** a supported install: the npm name is not owned by
  this project. See [`npm/README.md`](../npm/README.md).

## 2. First run (one minute, no configuration)

```bash
greenwash
```

You get a trust report for the current diff. Three things in it decide
everything else:

| Line | What to do with it |
|---|---|
| `Visible tests  N/N  (<command>)` | If it says `not run`, greenwash could not find a test command -- see step 4 |
| `Confidence: LOW` | Means **nothing was verified**. It is not a warning about your code; it is the tool refusing to imply more than it checked |
| `Suspicious patterns` | Read them. A `requires review` line is a question, not an accusation |

If it says the behavioral layer did not run, run `greenwash doctor`: it lists
what greenwash can and cannot see in this repository -- the test command, the
held-out suite, the integrity check, and the mode.

## 3. Choose how much of it you want

| Adopt this | Cost | Do it if |
|---|---|---|
| `greenwash` as a habit, before you merge | none -- it never blocks by default | always, for the first week |
| `greenwash --format markdown` in a PR description | none | reviewers ask "how do we know" |
| pre-commit: `greenwash scan --staged` | a few seconds per commit | you want the diff read before it lands |
| GitHub Action (`uses: 0DukePan/greenwash@v0.4.2`) | one job | you want CI to fail on a faked pass |
| Claude Code plugin | the hook runs on every turn end | your agent ends its own turns |
| Codex plugin | same, **strict by default** | same |
| `--enforce` / `--fail-on not_verified` | a red build on real failures | you have a held-out suite or a trustworthy baseline |
| `--strict` | reviews of every `requires_review` finding | you have decided the review cost is worth it |

The order matters. Adopt the reporting habit before the gate: a gate that
blocks on a finding nobody has read is how a tool gets uninstalled, and the
whole design of this one assumes a human is still in the loop.

## 4. Configure only what discovery gets wrong

`greenwash init` writes `.greenwash/config.json` with what it found. Every key
is an override, and the file is optional.

```json
{
  "test_command": "\"python\" -m pytest -q",
  "heldout": "tests/heldout",
  "timeout": 120,
  "mode": "report"
}
```

- **`test_command`** -- pin it when discovery guesses wrong (a monorepo, a
  `make test`, a container). Without a test command the report says the
  behavioral layer did not run rather than implying it passed.
- **`heldout`** -- a path or a command for a suite the agent never saw. This is
  the single highest-value configuration in the file: it is the only check that
  disagrees with a suite the agent edited, and almost nobody sets it up until
  they have been burned once. A directory of tests excluded from the agent's
  view, or a command that runs a private suite, both work.
- **`timeout`** -- seconds per test run. Raise it for slow suites; the process
  tree is killed on expiry (`killpg` on POSIX, `taskkill /T` on Windows).
- **`mode`** -- `report` (default), `enforce`, or `strict`.

## 5. If you turn on the gate, decide how findings get resolved

A gate with no path to "this one is fine, and here is why" is a gate people
route around. The supported path is a waiver:

```bash
greenwash waive \
  --rule GW-DIV-002 \
  --path src/loader.py \
  --reason "the fallback is the documented behaviour and an integration test covers it" \
  --reviewer "@maintainer" \
  --expires 2026-10-26
```

It writes one entry to `.greenwash/waivers.json`, which is committed with the
code. The rules are in [WAIVER_POLICY.md](./WAIVER_POLICY.md); the short
version is that a waiver binds one finding, has a name and a reason on it, and
lapses in at most 30 days.

Two conventions worth adopting at the same time:

- **Put `.greenwash/waivers.json` under CODEOWNERS**, so a waiver needs the same
  review as the code it excuses.
- **Never add a rule to `ignore_rules` in strict mode.** It is refused there by
  design: a suppressed rule applies to every finding it will ever produce, with
  no reviewer and no expiry, and the report can no longer tell you what it was
  hiding.

## 6. Know the failure modes before your team hits them

| Symptom | Cause | Fix |
|---|---|---|
| `VERIFICATION_FAILED`, "the test runner never started" | pytest (or the runner) is not installed in the environment greenwash ran in | install it, or set `test_command` to one that works |
| `not a git repository`, exit 3 | greenwash needs a commit to diff against | commit once; or run `greenwash scan --staged` |
| `analysed only what changed under <dir>` | you ran it in a subdirectory of a larger repo | run it from the repository root for a whole-repo report |
| A test that needs the network hangs until the timeout | the suite is not hermetic | set `timeout`, or point `test_command` at the hermetic subset |
| Confidence `LOW` on a clean diff | nothing was *verified* | that is the design; add a test command or a held-out suite |
| A finding that is correct, repeatedly | a real pattern the rules do not know about | waive it once, and open an issue: every confirmed false positive becomes a test |

## 7. Rolling it back

```bash
greenwash config: set "mode": "report"     # the gate stops blocking
```

or delete `.greenwash/config.json` and drop the hook from your host. Nothing
greenwash does is irreversible: it never writes to your code, and the only file
it creates on its own is the config. A tool you cannot turn off is a tool you
would route around instead, which is why every gate here is opt-in.

## 8. What to watch after a month

If you want your adoption to produce evidence rather than vibes, keep these
four numbers and publish them the way this project publishes its own -- including
when they are bad:

1. **Findings that were real** -- how many flags led to an actual fix.
2. **False positives** -- how many were wrong, and whether they were a known
   class ([false-positives.md](./false-positives.md)).
3. **Waivers used** -- and how many expired without anyone noticing.
4. **Blocked turns** -- if you run the strict profile, how often a turn was
   handed back, and whether it ended in a fix or a waiver.

The third and fourth are the honest cost of the gate. If they are high and
nothing upstream changes, strict mode is not earning its keep in your
repository, and the reported profile is the right one to go back to.
