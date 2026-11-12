# Releasing greenwash

The repo ships as a Claude Code plugin (and as a plain CLI / pre-commit hook /
GitHub Action). A release is a git tag that the marketplace, the GitHub Action
and pre-commit reference -- plus, now, a PyPI upload that makes
`pipx install greenwash-cli` true.

## The current state, stated plainly

`greenwash-cli` is **not on PyPI yet**. The wheel builds and installs cleanly
from the tag, so the supported install today is:

```bash
pipx install git+https://github.com/0DukePan/greenwash@v0.5.0
```

The README says so. Do not put `pipx install greenwash-cli` back in any page
until the file exists at <https://pypi.org/project/greenwash-cli/> -- an install
instruction that does not work is the same defect this tool exists to catch.

## First-time setup

This checkout is already initialized, on `main`, and points at
`git@github.com:0DukePan/greenwash.git`. These are the equivalent steps for a
plain copy:

```bash
git init
git add -A
git commit -m "greenwash 0.3.0"
git branch -M main
git remote add origin git@github.com:0DukePan/greenwash.git
git push -u origin main
```

### PyPI Trusted Publishing (once, by whoever owns the account)

The release workflow authenticates with OIDC; no token is stored and there is
no secret to rotate.

1. Claim the name. If `greenwash-cli` is unregistered the first upload creates
   it; if it is taken, the distribution has to change before anything else
   happens.
2. Add a Trusted Publisher at
   `https://pypi.org/manage/project/greenwash-cli/settings/publishing/`:
   owner `0DukePan`, repository `greenwash`, workflow `release.yml`,
   environment `pypi`.
3. Create the `pypi` environment in the repository's settings.

## Cut a release

1. Bump the version in **four** places -- the release workflow fails if the tag
   and `greenwash.__version__` disagree: `pyproject.toml`,
   `greenwash/__init__.py`, `.claude-plugin/plugin.json`, and
   `benchmark/plugins/greenwash-skill-only/.claude-plugin/plugin.json`.
2. Move the changelog's `Unreleased` section under the new version.
3. Tag it. Claude Code can create the tag for you, validating that
   `plugin.json` and any marketplace entry agree:

   ```bash
   claude plugin tag .
   ```

   Or by hand:

   ```bash
   git tag -a v0.5.0 -m "greenwash 0.5.0"
   git push origin v0.5.0
   ```

Pushing the tag runs `.github/workflows/release.yml`, which builds, checks the
metadata, runs `benchmark/verify.py` and the product gate, installs the built
wheel into a clean environment and asserts the demo cheat is still caught --
and only then uploads.

## Before tagging

Run the same gate CI runs:

```bash
python benchmark/verify.py            # 90 seconds, no model
python -m pytest -q -m "not program"  # the product gate
python demo/run_demo.py
python -m build --wheel --outdir dist && python -m twine check dist/*
claude plugin validate .
```

A release that cannot pass its own gate does not reach the registry.

## After the first upload

```bash
pipx install greenwash-cli          # now true
python -m venv /tmp/check && /tmp/check/bin/pip install greenwash-cli
/tmp/check/bin/greenwash --version  # the released version
```

Then change the install lines in `README.md`, `docs/ADOPTION_GUIDE.md` and
`docs/launch-post.md` from `git+https://...` back to the distribution name, and
turn the "not on PyPI yet" note into a link to the project page.

## The benchmark is separate

A release does **not** require fresh benchmark numbers, but the README's
headline claim does. The number is produced by the manual `benchmark`
workflow (or locally); see [`benchmark/README.md`](./benchmark/README.md).

## What a tag does not include

The PyPI upload is the CLI. The Claude plugin is read from the repository by
`/plugin marketplace add`, the GitHub Action from the tag by `uses:`, and
pre-commit by `rev:`. All three work without PyPI, which is why the repository
is usable before the first upload -- and why the upload is the last mile rather
than the foundation.
