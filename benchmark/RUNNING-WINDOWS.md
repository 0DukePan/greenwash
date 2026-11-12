# Running the DeepSeek benchmark: copy-paste, Windows

You are probably in the wrong folder. The first error is almost always
`can't open file 'benchmark/deepseek_run.py'`, which means the terminal is not
in the repository.

## 1. Go to the repository

```bat
cd /d D:\Desktop\busted
```

`cd /d` changes drive too, in case you started on `C:`.

Check you are in the right place — this should list `benchmark`, `greenwash`
and `tests`:

```bat
dir /b
```

## 2. Prove the wiring works (no API key needed)

```bat
python benchmark\deepseek_run.py --selfcheck
```

Expect: `selfcheck: OK -- harness, classifier, evidence and row shape are wired; only the API is untested`

This runs the real harness against a scripted agent on one task and checks the
row it produces. If this fails, the problem is the checkout, not the model.

## 3. Check the API key and balance

```bat
python benchmark\deepseek_run.py --preflight
```

- `preflight: OK model=deepseek-v4-pro ...` — you are ready. Go to step 4.
- `preflight: the account has no balance.` — top up the DeepSeek account that
  owns the key. Nothing else will work until then, and no rows are written.

## 4. The pilot run: 24 sessions

`cmd.exe` does **not** use `\` to continue a line. Either write it on one line,
or use `^` at the end of each line. One line is safest:

```bat
python benchmark\deepseek_run.py --states off,full --runs 3 --task add-subtract-swap --task is-palindrome-stub --task json-load-default --task backoff-delay
```

Or with continuation, every line ending in a caret (no space after it):

```bat
python benchmark\deepseek_run.py --states off,full --runs 3 ^
  --task add-subtract-swap --task is-palindrome-stub ^
  --task json-load-default --task backoff-delay
```

Rows stream to `benchmark\results\deepseek.jsonl` as they finish, so an
interruption costs nothing: rerun the same command with `--resume` added.

## 5. Read the result

```bat
python benchmark\deepseek_run.py --report
```

## 6. The full run, only if the pilot showed a difference

```bat
python benchmark\deepseek_run.py --states off,skill-only,full --runs 3 --resume
```

That is 261 sessions. `--resume` skips whatever is already in the jsonl.

## Using PowerShell or Git Bash instead

| Shell | Change directory | Line continuation |
|---|---|---|
| `cmd.exe` | `cd /d D:\Desktop\busted` | `^` at end of line |
| PowerShell | `cd D:\Desktop\busted` | `` ` `` (backtick) at end of line |
| Git Bash | `cd /d/Desktop/busted` | `\` at end of line |

In Git Bash the repository is `/d/Desktop/busted`, not `D:\Desktop\busted`.

## If `python` is not found

This machine has Python 3.14 on PATH as `python`, and a 3.10 virtualenv at
`.venv` that has pytest but no dependencies of its own. Use `python`; if the
shell cannot find it, `py -3` is the launcher equivalent:

```bat
py -3 benchmark\deepseek_run.py --selfcheck
```
