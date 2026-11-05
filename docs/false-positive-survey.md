# False-positive survey: 10 repositories, 250 commits

The scanner is run over real commit history and every flag is listed for a
human to judge. This is a **survey, not a rate**: nobody labelled the changes
that were *not* flagged, the repositories were not sampled, and the clones are
shallow (the last 25 commits of each default branch). What it can say is what
fired, on what, and whether a human would accept it.

It was run twice. The first run found that one asking rule was 95% of the
noise, the rule was narrowed, and the second run measures the result against
the same history. Both runs are published.

Reproduce with:

```bash
git clone --depth 30 https://github.com/pallets/flask.git   # × the table below
python benchmark/fp_survey.py --limit 25 flask requests httpx pytest llm \
    axios express got chalk koa
```

Artifact: `benchmark/results/fp-survey.json` (every flag, with path and commit).
The second run is the committed artifact.

## What was scanned

| Repository | Commits | File changes | Flags before | Flags after |
|---|---:|---:|---:|---:|
| `axios` | 25 | 168 | 11 | 0 |
| `chalk` | 25 | 84 | 6 | 2 |
| `express` | 25 | 53 | 15 | 0 |
| `flask` | 25 | 96 | 20 | 4 |
| `got` | 25 | 125 | 1 | 1 |
| `httpx` | 25 | 47 | 5 | 0 |
| `koa` | 25 | 50 | 5 | 0 |
| `llm` | 25 | 65 | 1 | 1 |
| `pytest` | 25 | 290 | 12 | 4 |
| `requests` | 25 | 51 | 33 | 0 |
| **total** | **250** | **1,029** | **109** | **12** |

Python and JavaScript / TypeScript only, static layer only -- no test suite was
executed for this survey, so none of the behavioral rules could fire.

## Run 1: one asking rule was the noise

| Rule | Flags | Asks or accuses |
|---|---:|---|
| `verifier-config-changed` | 104 | asks (needs review) |
| `conftest-changed` | 3 | asks (needs review) |
| `assertion-weakened` | 1 | accuses |
| `swallowed-exception` | 1 | accuses |

104 of 109 flags were one rule: 94 on GitHub workflows and
`.pre-commit-config.yaml`, 10 on manifests. The files that carried it:

- `.github/workflows/*.yml` -- 76 flags
- `.pre-commit-config.yaml` -- 18 flags
- `package.json` / `pyproject.toml` -- 10 flags
- `tox.ini` -- 2 flags

Not one was a tamper: dependency bumps, action-version updates, lint
configuration. In strict mode every one of them blocks the turn until somebody
waives it -- roughly one review every 2.4 commits. The rule was fixed rather
than the finding being waived: it now asks only when a change can alter what
runs, and a version reference is not that.

## Run 2: after the narrowing

| Rule | Flags | Asks or accuses |
|---|---:|---|
| `verifier-config-changed` | 7 | asks (needs review) |
| `conftest-changed` | 3 | asks (needs review) |
| `assertion-weakened` | 1 | accuses |
| `swallowed-exception` | 1 | accuses |

**The 104 became 7, and all seven are real changes to runner configuration:**

| Repository | Commit | File | What changed |
|---|---|---|---|
| `chalk` | `7211001` | `package.json` | the `test` script switched from `ava` to `node --test` |
| `chalk` | `8a94e0e` | `package.json` | the `test` script changed again in the same migration |
| `flask` | `6a2f545` | `.pre-commit-config.yaml` | a hook gained `additional_dependencies` and lost an `args` line |
| `pytest` | `4abdff3` | `.pre-commit-config.yaml` | a hook gained an `exclude:` for release notes |
| `pytest` | `ed37b23` | `.pre-commit-config.yaml` | the same exclude, seen through a second commit |
| `pytest` | `ed37b23` | `tox.ini` | a test environment gained a dependency |
| `pytest` | `4abdff3` | `tox.ini` | the same dependency, seen through a second commit |

Two of the seven are one change seen through two commits; the rest are distinct.
No accusatory flag changed, because the narrowing was about the asking rules.

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
  "One review every 2.4 commits" is the pre-fix arithmetic on this sample.
- **Not representative.** No Go, Rust, Ruby or Java repositories; no monorepos;
  no repository whose tests were actually modified to cheat.
- **A narrowed rule sees less.** The seven that remain are the changes the new
  trigger can see. A bypass written as a shell script in a separate file, or a
  test job replaced by a no-op with the same name, is still a partial-coverage
  gap and the taxonomy says so.

## What it says to do next

The gate's noise floor on this sample moved from 104 reviews to 7, and every
one of the seven is a change a reviewer would want to see. The next measurement
is not another corpus: it is whether a team leaves the gate on for a week.
