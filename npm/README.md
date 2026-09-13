# greenwash (npm)

`npx greenwash` -- a shim that runs the Python implementation.

```bash
npx greenwash                      # a trust report for the current diff
npx greenwash scan                 # static analysis only
npx greenwash --enforce            # opt in to blocking exit codes
```

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
pipx install greenwash     # recommended: isolated, on your PATH
pip install greenwash      # or into the current environment
```

With the Python package installed, `npx greenwash` and `greenwash` are the same
program with the same output and the same exit codes.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | report mode always; `--enforce` when verified |
| 1 | `scan` / `verify` found something; `--enforce` when not verified |
| 2 | `--enforce` and the verdict was suspicious |
| 3 | could not run (no Python, no package, not a git repository) |

Full documentation: <https://github.com/0DukePan/greenwash>
