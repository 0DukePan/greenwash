# Releasing greenwash

The repo ships as a Claude Code plugin (and as a plain CLI / pre-commit hook /
GitHub Action). A release is just a git tag that the marketplace and the
GitHub Action can reference.

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

## Cut a release

1. Bump `version` in `.claude-plugin/plugin.json` (and the sibling under
   `benchmark/plugins/greenwash-skill-only/` if it changed).
2. Add the version to `CHANGELOG.md`.
3. Tag it. Claude Code can create the tag for you, validating that
   `plugin.json` and any marketplace entry agree:

   ```bash
   claude plugin tag .
   ```

   Or by hand: `git tag v0.3.0 && git push --tags`.
4. If you publish the benchmark numbers for this version, write them to
   `benchmark/RESULTS.md` (produced by `python benchmark/report.py --out …`)
   and reference the tag in the commit.

## Before tagging

Run the same gate CI runs:

```bash
python -m pytest -q
python demo/run_demo.py
claude plugin validate .
```

## The benchmark is separate

A release does **not** require fresh benchmark numbers, but the README's
headline claim does. The number is produced by the manual `benchmark`
workflow (or locally); see [`benchmark/README.md`](./benchmark/README.md).
