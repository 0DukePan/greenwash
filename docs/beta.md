# Report-only beta

The smallest useful way to try greenwash on a real repository: run it, read its
report, and let it fail nothing. No account, no telemetry, no network calls, no
dependencies beyond Python 3.10+.

## Install

```
git clone https://github.com/0DukePan/greenwash
cd greenwash
python scripts/greenwash_check.py --help
```

The checker is stdlib-only. There is nothing to pip-install.

## Run it on a change

From your repository, with the change in the working tree:

```
python /path/to/greenwash/scripts/greenwash_check.py scan --json
```

With tests and the stronger checks (this runs your test command):

```
python /path/to/greenwash/scripts/greenwash_check.py all \
  --run-tests "pytest -q" --json
```

Exit codes: `0` clean, `1` findings, `2` suspicious, `3` could not check,
`4` the checker's own inputs failed integrity, `64` usage. In report-only mode
ignore all of them except `3`/`4`.

## CI, report-only

`.github/workflows/greenwash-report-only.yml` in this repository is the
template. It runs on `pull_request` with read-only permissions and no secrets,
captures the JSON, writes a job summary, uploads an artifact, and never fails
the job. Drop it into a repository and read the artifact for a week before
deciding whether the checker may block anything.

## The demo

`demo/twin-pair/` holds two changes to the same test file with real captured
output: one assertion removed (flagged `assertion-weakened`, exit 1), one
assertion added (clean, exit 0). The page states plainly that these are
maintainer-authored fixtures, not evidence of a rate.

## Measured overhead

Static scan (`scan --json`, no test execution), median of three runs per repo,
on Windows 11, Python 3.14, warm filesystem. Numbers are millisecond wall time
for the whole process, so Python startup is included and dominates at this
size.

| Repository | Clean tree | One test file changed |
|---|---|---|
| `pallets/itsdangerous` (shallow clone) | 352.3 ms | 401.2 ms |
| `psf/cachecontrol` (shallow clone) | 726.6 ms | 397.1 ms |
| this repository | 426.9 ms | 405.5 ms |

Reading: every run is sub-second, and the spread between the clean and changed
tree is within run-to-run noise (the cachecontrol clean run was an outlier).
The cost of a report-only check at these sizes is Python startup plus one diff,
not test execution. Replay mode adds the project's own test time; that was not
measured here and is not claimed.

## What this beta does not do

- It does not claim detection quality. The only licensed sentences are in the
  [claim matrix](../docs/claim-matrix.md) and `docs/what-did-not-work.md`.
- It does not post comments on anyone's repository by itself. The workflow
  uploads an artifact and writes a summary in the same job.
- It does not run tests unless you pass `--run-tests`, and it does not phone
  home: there is no telemetry code path.
