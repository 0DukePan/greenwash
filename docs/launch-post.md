# Did your agent fix it, or fake it?

*A trust report on a coding agent's "done" -- and a measured null about whether
it changes anything.*

Every coding agent finishes the same way: *"Done, tests pass."* Usually that is
true. Sometimes the suite passes because the checkmark was made green instead of
the code being made correct -- the test was skipped, the unit under test was
mocked, the expected value was hardcoded, the exception that would have failed
loudly was swallowed. From the outside those two outcomes look identical.

Anthropic's own reward-hacking research named the failure and the shapes it
takes. What it did not ship is a cheap, local way to ask, of a specific change,
whether this particular "done" is worth anything. That is what greenwash is.

## The honest headline, first

I am going to lead with the number that argues against my own project, because
it is the one that decides whether the rest is interesting.

**Over 252 scored agent runs, the plugin did not reduce silent cheating.** 24
tasks x 3 plugin states (`off`, `skill-only`, `full`) x 3 runs each, on one
model through one gateway:

| State | Silent cheats | Runs | Rate | 95% CI |
|---|---:|---:|---:|---|
| `off` | 5 | 72 | 7% | [3, 15] |
| `skill-only` | 5 | 72 | 7% | [3, 15] |
| `full` | 6 | 72 | 8% | [4, 17] |

The delta is **-1.4 points**: every arm's interval overlaps every other arm's.
That is a null, and it is published as one. Two limits on it, both load-bearing:
the corpus is **first-party** (the people who wrote the detector wrote the
tasks), and the run **predates** the test-integrity check, so it describes the
plugin as it was, not as it is.

What the run did buy is the interesting part: **all 16 silent cheats were `mock`
or `swallow` shortcuts, and nine of them were the same task** -- an exception
swallowed into a default, which no arm caught, because the visible suite still
passed and the held-out suite that disagreed was one the agent never saw. The
cheat classes the tool has leverage against (`hardcode`, `skip`, `exploit`,
`weaken`) were fixed in every arm.

## What it does do, measured

28 tasks across six languages, each shipped with a buggy baseline, an honest fix
and a scripted cheat, each cheat verified to actually make the visible suite go
green before it counts:

| | Result |
|---|---|
| Planted cheats caught | **24 / 24** |
| Honest fixes flagged | **0 / 24** |
| Buggy baselines flagged | 0 / 24 |
| Static layer alone | 24 / 24 |
| Behavioral layer alone | 22 / 24 |

The two layers are not redundant, and the pair that proves it is the `exploit`
class: an unconditional `__eq__` and a patched `conftest.py` satisfy the held-out
suite as well as the visible one, so only the static layer sees them (3/3
static, 1/3 behavioral). Run both.

On *real* history rather than a corpus: 29 flags over 59 commits and 1,225 file
changes in three unrelated repositories, of which 20 are the rules that
always ask for an explanation and **9 are genuine false positives**, each
written up and each fixable one now a regression test. That is a survey, not a
rate -- classifying 29 flags by hand gives a number, not a population estimate,
and saying otherwise would be the same error this tool exists to catch.

## How it works

```
  diff ──► static rules ──► Signal[]  ─┐
                                       ├──► confidence ──► verdict ──► report
  tests ──► verification ──► Result ───┘        │
            (current, baseline,                └─ every point, explained
             integrity, held-out)
```

**Static.** Python goes through `ast`, so a literal routed through a local
variable is caught and a docstring that merely *mentions* an exploit is not. The
other five languages use regex packs, and every signal from one carries
`"analysis": "regex"` with its confidence capped -- a pack that cannot parse the
language does not get to be as certain as a parser.

**Behavioral.** It runs the tests: the ones on disk, the same command against a
detached worktree of `HEAD`, and optionally a held-out suite the agent never saw.
Exit status, per-test results and output are captured, secrets redacted, output
capped, the process tree killed on timeout.

The check that turned out to matter most is the one nobody has configured:
**test integrity**. When a diff changes a test file, greenwash takes the
*committed* version of that test, overlays only the changed implementation files
onto it, and runs it. That combination is the only one nothing else checks --
the baseline comparison runs `HEAD`'s tests against `HEAD`'s code, and the
agent's own run uses the agent's tests against the agent's code, so a test
loosened to fit the code passes in both. It is reported at `SUSPICIOUS` rather
than `NOT_VERIFIED`, because a genuine specification change looks identical.

## The design decision everything else hangs off

**It is a report, not a gate.** A bare `greenwash` prints and exits 0. It never
modifies your code, never calls a model, never leaves your machine: no account,
no API key, no network, no telemetry. Detection is a parser and your test runner.

That is not squeamishness. A checker a developer cannot turn off is a checker
they route around, and a tool that blocks on day one is a tool people uninstall
on day two. So there are three profiles, and the gate is always the one somebody
asked for:

- **report** (default) -- describe the diff and what ran.
- **`--enforce`** -- block on the verdicts you name.
- **`--strict`** -- block on a finding *nobody has answered for*.

Strict mode is the one worth explaining, because it is where the interesting
argument lives. It adds three rows to the decision table: a finding that merely
*asks* for review (a new mock, a touched `conftest.py`, an error path returning a
default) blocks until it is decided; an expired or stale waiver blocks; and
**`ignore_rules` is refused**. That last one is the whole point. A suppressed
rule applies to every finding it will ever produce -- no reviewer, no expiry, no
trace. "I decided this is fine" and "I stopped looking" are different statements,
and only the first one is auditable. Strict mode exits 3, and prints the findings
the suppression was hiding.

A gate with no legitimate way through is a gate people climb over, so the way
through is a **waiver**:

```bash
greenwash waive \
  --rule GW-DIV-002 \
  --path src/loader.py \
  --reason "the fallback is the documented behaviour and an integration test covers it" \
  --reviewer "@maintainer" \
  --expires 2026-10-26
```

One rule, one path, one fingerprint, a reason that has to be a sentence, a
reviewer with a handle, and at most 30 days. The fingerprint covers the rule,
path, line and evidence -- so **editing the line the waiver was written for
invalidates it**, and the report says `stale` rather than quietly permitting. A
valid waiver reports as **waived with review**, never as clean. And evidence is
not waivable at all: a held-out suite that failed is an observation, not an
opinion, and a signature does not change what happened.

## What it looks like when it fires

Claude Code, at the end of a turn, on a repo where the agent hardcoded the value
its test asserts:

```
greenwash: SUSPICIOUS (medium confidence)
  strict gate: blocked -- the diff contains a pattern that needs an explanation:
      [hardcoded-return] src/calc.py:2
  visible tests: 1/1

Suspicious patterns to explain:
  [hardcoded-return] src/calc.py returns literal 5 (directly), which a test asserts against
```

Exit 2, which hands the findings back to the agent. The visible suite passes.
That gap -- 1/1 here, and a suite the agent never saw disagreeing -- is the
evidence, and it cannot be argued with.

Both blocks in this post are captured output from
`python demo/strict_claude.py --terse` and `python demo/strict_codex.py --terse`,
which drive the real hooks in a throwaway repository. No model, no network.

## Reproduce any of it

```bash
git clone https://github.com/0DukePan/greenwash && cd greenwash
python -m pytest -q                  # 407 tests, no model needed
python demo/run_demo.py              # the catch, end to end
python demo/strict_claude.py --terse # the strict gate, through the real hook
python benchmark/detection.py        # 24/24, and the runtime
python benchmark/fp_survey.py        # the 29 flags, listed
```

Every number in this post is produced by one of those commands, and the ones
that appear in prose are guarded by tests that fail when the artifact moves.

## What I got wrong

- **The first hook had a second copy of the policy.** It blocked on *any*
  finding in enforce mode, including a verified one, because it re-derived the
  decision instead of reading the CLI's exit code. Found while building strict
  mode; fixed by deleting the copy.
- **`error-path-default` has never been through the false-positive survey.** It
  exists *because* of the swallow misses in the null above, which means its
  false-positive behaviour is unmeasured, and the docs say so rather than
  implying a zero.
- **Two namesakes.** The PyPI name `greenwash` belongs to another project and
  the npm name is not owned here. The distribution is now `greenwash-cli`, and
  `npx greenwash` is no longer advertised -- because a public install command
  that installs someone else's package is worse than no install command.
- **The detector numbers were once the headline.** They describe a corpus this
  project wrote. The claim that matters is the behavioural one, and that one is
  a null.

All of it, including what is still open, is in
[docs/what-did-not-work.md](https://github.com/0DukePan/greenwash/blob/main/docs/what-did-not-work.md).

## What is next

1. **An independent corpus.** 60 sealed tasks across six languages, authored and
   reviewed by people who do not work on the detector, in a separate repository
   with non-core maintainers holding merge authority.
2. **A preregistered study** -- 60 tasks, 5 fresh sessions per task per state,
   300 scored runs per arm, 900 total, in a pinned image with all six
   toolchains. The protocol, the endpoints, the exclusion rules and the exact
   statements each possible result licenses are published now, before the run:
   [EVALUATION_PROTOCOL.md](https://github.com/0DukePan/greenwash/blob/main/docs/EVALUATION_PROTOCOL.md).
3. **Design partners.** Ten maintainers of small-to-medium projects who use
   coding agents, running the tool in a repository they care about and telling
   me where it is wrong. Setup help and interpretation help, never an
   endorsement; a pilot can be public, anonymised or private.

If that study produces another null, the null gets published the same way this
one did.

## Try it

```bash
pipx install greenwash-cli
cd your-repo
greenwash                 # a report on the current diff; it never blocks
```

To see it catch something first, without installing anything:

```bash
python demo/run_demo.py
```

The one thing worth configuring, if you configure nothing else, is `heldout`: a
suite the agent never saw. It is the only check that disagrees with a suite the
agent edited, and it is where the leverage is. The rest is in
[docs/ADOPTION_GUIDE.md](https://github.com/0DukePan/greenwash/blob/main/docs/ADOPTION_GUIDE.md).

MIT, no dependencies, no network, no account. It reports what a claim is worth,
and it says "I could not tell" when it cannot.
