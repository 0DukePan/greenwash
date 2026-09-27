# greenwash (npm)

A shim that runs the Python implementation.

```bash
npx greenwash                      # a trust report for the current diff
npx greenwash scan                 # static analysis only
npx greenwash --enforce            # opt in to blocking exit codes
npx greenwash --strict             # the profile the agent plugins run
```

## Not on the registry yet

**`npx greenwash` installs a different project today.** This package name is not
owned by this project and has not been published under it, so the commands above
work only after `npm pack` inside this directory and a local install of the
tarball:

```bash
cd npm && npm pack && npm install -g ./greenwash-0.4.2.tgz
```

Until that name is verified, the supported install is the Python distribution --
and the guidance below is what the shim prints when it cannot find it.

## This is a wrapper, not a port

The detector, the behavioral verifier and the report all live in the Python
package. Reimplementing them here would mean two codebases that can disagree
about whether someone's tests pass, which is exactly the failure this tool
exists to catch. So this package finds a Python interpreter, checks that
`greenwash` is importable, and hands over argv and the exit code unchanged.

If the Python package is missing, it says so and tells you the two commands that
install it. Everything greenwash does is local: no account, no API key, no
network, no telemetry.

## Installing the real thing

```bash
pipx install greenwash-cli     # recommended: isolated, on your PATH
pip install greenwash-cli      # or into the current environment
```

The distribution is `greenwash-cli`; the import name and the command it installs
are both `greenwash`. (There is an unrelated project on PyPI called `greenwash`,
which is why the distribution is named differently.)

With the Python package installed, `npx greenwash` and `greenwash` are the same
program with the same output and the same exit codes.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | report mode when a report is produced; `--enforce` or `--strict` when verified |
| 1 | `scan` / `verify` found something; `--enforce`/`--strict` when not verified |
| 2 | `--enforce`/`--strict` and the verdict was suspicious, or a finding nobody has waived |
| 3 | could not run (no Python, no package, not a git repository); or the verification could not complete |

Full documentation: <https://github.com/0DukePan/greenwash>
