# False-positive survey: 10 repositories, 250 commits

The scanner is run over real commit history and every flag is listed for a
human to judge. This is a **survey, not a rate**: nobody labelled the changes
that were *not* flagged, the repositories were not sampled, and the clones are
shallow (the last 25 commits of each default branch). What it can say is what
fired, on what, and whether a human would accept it.

It was run twice. The first run found that one asking rule was 95% of the
noise, the rule was narrowed, and the second run measures the result against
the same history. That second run was then repeated after a fix to the survey
harness let it see `error-path-default`, a rule that parses the file and had
never been measured; the fix added two flags and moved nothing else. Both runs
are published, and every count below is the last run.

Reproduce with:

```bash
mkdir -p /tmp/gw_fp && cd /tmp/gw_fp
git clone --depth 30 --single-branch https://github.com/axios/axios.git
git clone --depth 30 --single-branch https://github.com/chalk/chalk.git
git clone --depth 30 --single-branch https://github.com/expressjs/express.git
git clone --depth 30 --single-branch https://github.com/pallets/flask.git
git clone --depth 30 --single-branch https://github.com/sindresorhus/got.git
git clone --depth 30 --single-branch https://github.com/encode/httpx.git
git clone --depth 30 --single-branch https://github.com/koajs/koa.git
git clone --depth 30 --single-branch https://github.com/simonw/llm.git
git clone --depth 30 --single-branch https://github.com/pytest-dev/pytest.git
git clone --depth 30 --single-branch https://github.com/psf/requests.git
cd -
python benchmark/fp_survey.py --limit 25 \
    /tmp/gw_fp/axios /tmp/gw_fp/chalk /tmp/gw_fp/express /tmp/gw_fp/flask \
    /tmp/gw_fp/got /tmp/gw_fp/httpx /tmp/gw_fp/koa /tmp/gw_fp/llm \
    /tmp/gw_fp/pytest /tmp/gw_fp/requests
```

Artifact: `benchmark/results/fp-survey.json` (every flag, with path and commit).
The second run is the committed artifact, and `tests/test_launch_docs.py` fails
when a row below disagrees with it.

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
| `pytest` | 25 | 290 | 12 | 6 |
| `requests` | 25 | 51 | 33 | 0 |
| **total** | **250** | **1,029** | **109** | **14** |

Python and JavaScript / TypeScript only, static layer only -- no test suite was
executed for this survey, so none of the behavioral rules could fire. The
`before` column is the pre-narrowing run and exists only in this page; the
`after` column is checked against the committed artifact, so it cannot drift
from the data it quotes.

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

## Run 2: after the narrowing, with the blind rule measured

| Rule | Flags | Asks or accuses |
|---|---:|---|
| `verifier-config-changed` | 7 | asks (needs review) |
| `conftest-changed` | 3 | asks (needs review) |
| `error-path-default` | 2 | asks (needs review) |
| `assertion-weakened` | 1 | accuses |
| `swallowed-exception` | 1 | accuses |

The split is 14 flags: 12 asking, 2 accusatory -- the same two accusations as
the first run.

**The 104 became 7, and all seven are real changes to runner configuration.**
Every flag in the run:

| Repository | Commit | File | Rule | Judgment |
|---|---|---|---|---|
| `chalk` | `7211001` | `package.json` | `verifier-config-changed` | the `test` script switched from `ava` to `node --test` |
| `chalk` | `8a94e0e` | `package.json` | `verifier-config-changed` | the `test` script changed again in the same migration |
| `flask` | `6a2f545` | `.pre-commit-config.yaml` | `verifier-config-changed` | a hook gained `additional_dependencies` and lost an `args` line |
| `pytest` | `4abdff3` | `.pre-commit-config.yaml` | `verifier-config-changed` | a hook gained an `exclude:` for release notes |
| `pytest` | `ed37b23` | `.pre-commit-config.yaml` | `verifier-config-changed` | the same exclude, seen through a second commit |
| `pytest` | `ed37b23` | `tox.ini` | `verifier-config-changed` | a test environment gained a dependency |
| `pytest` | `4abdff3` | `tox.ini` | `verifier-config-changed` | the same dependency, seen through a second commit |
| `flask` | `6a2f545` | `tests/conftest.py` | `conftest-changed` | the `stable` merge; the fixture refactor arrives with it |
| `flask` | `548994e` | `tests/conftest.py` | `conftest-changed` | a `monkeypatch` fixture refactor -- fixture hygiene, nothing masks a failure |
| `llm` | `71141a8` | `tests/conftest.py` | `conftest-changed` | a fixture renamed a mocked model -- ordinary test housekeeping |
| `pytest` | `564d690` | `src/_pytest/approx.py` | `error-path-default` | a true ask: the fix landed with no test (see below) |
| `pytest` | `4b3bb3c` | `src/_pytest/approx.py` | `error-path-default` | a false positive: the merge carries the regression test (see below) |
| `flask` | `f2ef7a5` | `tests/test_basic.py` | `assertion-weakened` | a false positive: the narrower `pytest.raises` implies the removed type assertion |
| `got` | `50c4ac6` | `test/create.ts` | `swallowed-exception` | a false positive: a deliberate empty `catch {}` with assertions after it |

Two of the verifier flags are one change seen through two commits, and so are
the two `error-path-default` flags; the rest are distinct. No accusatory flag
changed, because the narrowing was about the asking rules.

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

## The rule the survey could not see until the harness was fixed

`error-path-default` reads the parsed Python file, not only the diff, so the
first two passes could not see it at all: `fp_survey.py` scanned every diff
from the greenwash checkout, which meant the rule parsed `src/_pytest/approx.py`
against this repository, found no such file, and returned no module. The
survey said nothing about the rule because the instrument was blind, not
because the history was clean. Scanning each diff with the repository it came
from as the working directory fixed that, and the rest of the artifact did not
move -- same twelve flags, same files, same commits.

On the same 250 commits the rule fires twice, both on one change in `pytest`:

**`pytest` `564d690` (`Fix pytest.approx regression with JAX arrays`) -- a true
ask.** The diff wraps `getattr(expected, "flat", expected)` in `try / except
NotImplementedError: return False`, and nothing in this commit tests it. The
regression test arrived six commits later in the same pull request (`df640bc`,
merged as `4b3bb3c`). Asking "where is the test?" at `564d690` is asking the
right question, and the branch answered it before merge. The returned `False`
is correct -- a JAX array cannot contain a `Decimal` -- so this is a coverage
gap the rule caught while it was open, not a cheat.

**`pytest` `4b3bb3c` (the merge of that pull request) -- a false positive.**
The surveyed diff is the merge against its first parent, so it contains both
the handler and the regression test
`testing/python/approx.py::TestApprox::test_custom_array_unimplemented_flat`,
which raises `NotImplementedError` from `flat` and asserts the `approx` result.
The rule's premise -- no related test file mentions that path -- is false at
this commit. It missed the test because its related-test lookup only guesses a
sibling `test_<stem>.py` or a `tests/`, `test/` or `__tests__/` directory, and
pytest keeps its tests in `testing/`. That guess list is a rule change, not a
docs change: widening it needs its own measurement.

Two flags on one change in 250 commits, one of them a false positive with a
named cause. The rule's measured history is now that, not a blank.

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
- **AST rules read the clone's checkout, not each commit's tree.** A parsed
  file is the default branch's copy; every flag is confirmed by reading the
  commit, and the two `error-path-default` flags are exactly one change seen
  through a commit and its merge.
- **`error-path-default`'s suppression heuristic is not measured.** It asks
  only when no nearby test file mentions the function or the exception; the
  merge flag above is that heuristic failing to look in `testing/`.

## What it says to do next

The gate's noise floor on this sample moved from 104 reviews to 7, and every
one of the seven is a change a reviewer would want to see. The one rule that
had never been measured now has a measured history -- two flags, one change,
zero cheats -- and it is the fifth asking rule on the page rather than an
unmeasured blank. The next measurement is not another corpus: it is whether a
team leaves the gate on for a week.
