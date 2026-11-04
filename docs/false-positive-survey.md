# False-positive survey: 10 repositories, 250 commits

The scanner is run over real commit history and every flag is listed for a
human to judge. This is a **survey, not a rate**: nobody labelled the changes
that were *not* flagged, the repositories were not sampled, and the clones are
shallow (the last 25 commits of each default branch). What it can say is what
fired, on what, and whether a human would accept it.

Reproduce with:

```bash
git clone --depth 30 https://github.com/pallets/flask.git   # × the table below
python benchmark/fp_survey.py --limit 25 flask requests httpx pytest llm \
    axios express got chalk koa
```

Artifact: `benchmark/results/fp-survey.json` (every flag, with path and commit).

## What was scanned

| Repository | Commits | File changes | Flags |
|---|---:|---:|---:|
| `axios` | 25 | 168 | 11 |
| `chalk` | 25 | 84 | 6 |
| `express` | 25 | 53 | 15 |
| `flask` | 25 | 96 | 20 |
| `got` | 25 | 125 | 1 |
| `httpx` | 25 | 47 | 5 |
| `koa` | 25 | 50 | 5 |
| `llm` | 25 | 65 | 1 |
| `pytest` | 25 | 290 | 12 |
| `requests` | 25 | 51 | 33 |
| **total** | **250** | **1,029** | **109** |

0.44 flags per commit; one flag per 9.4 changed files. Python and JavaScript /
TypeScript only, static layer only -- no test suite was executed for this
survey, so none of the behavioral rules could fire.

## What fired

| Rule | Flags | Asks or accuses |
|---|---:|---|
| `verifier-config-changed` | 104 | asks (needs review) |
| `conftest-changed` | 3 | asks (needs review) |
| `assertion-weakened` | 1 | accuses |
| `swallowed-exception` | 1 | accuses |

**104 of the 109 flags are one asking rule firing on ordinary maintenance.**
The files that carried `verifier-config-changed`:

- `.github/workflows/*.yml` -- 76 flags
- `.pre-commit-config.yaml` -- 18 flags
- `package.json` / `pyproject.toml` -- 6 flags
- `tox.ini` -- 2 flags
- `tests/**/package.json` -- 2 flags

Not one of those was a tamper: they are dependency bumps, action-version
updates, and lint configuration. In report mode that is noise next to honest
work. In strict mode every one of them blocks the turn until somebody waives
it, which is roughly one review every 2.4 commits in this sample. That is the
real cost of the strict gate, and it is measured here for the first time.

## The two flags that accused, checked by hand

**`flask` `f2ef7a5` (`werkzeug 3.2 compat`) -- `assertion-weakened` in
`tests/test_basic.py`: false positive.** The diff narrows
`pytest.raises(KeyError)` to `pytest.raises(BadRequestKeyError)`, removes
`assert exc_info.errisinstance(BadRequest)` and
`assert "missing_key" in exc_info.value.get_description()`, and adds
`assert "missing_key" in exc_info.value.get_response().get_data(as_text=True)`.
The removed type assertion is implied by the narrower expected exception, and
the message check moves to the response body. Coverage did not weaken; the rule
counted two removed assertions and one added one.

**`got` `50c4ac6` (`Simplify`) -- `swallowed-exception` in `test/create.ts`:
false positive.** The added `try { ...merge(...) } catch {}` is followed by
assertions on the state the merge produced. The empty catch is the test
deliberately not caring whether the call throws, not an error being hidden from
a result.

Two accusatory flags, both wrong, in 250 commits. They are the class
[false-positives.md](./false-positives.md) already documents: a test edit that
looks like weakening and an empty handler that is deliberate.

## What this does not measure

- **Not a false-positive rate.** 10 repositories, 25 commits each, chosen by
  hand. The answer to "how often is a green scan wrong?" needs labels on the
  commits that were *not* flagged, which nobody here produced.
- **Not the strict-mode experience.** It counts blocks, not how annoying a
  block is, how long a waiver takes, or whether a team would keep the gate.
- **Not representative.** No Go, Rust, Ruby or Java repositories; no monorepos;
  no repository whose tests were actually modified to cheat.

## What it says to do next

The verdict on the scanner is good; the verdict on the strict gate's noise is
bad, and it is one rule. `verifier-config-changed` should distinguish "this
change alters what runs" (a test command, a `conftest.py`-like hook, a skip in
CI) from "this change bumps an action version or a dependency", or drop
`.github/workflows/*` and dependency manifests from the rule entirely. Until
then, strict mode on a repository with active CI is a waiver queue, and a
waiver queue is the thing people route around.
