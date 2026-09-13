# Task template

Copy this directory to `benchmark/tasks/<your-task-name>/` and edit it into a
real task. Directories whose name starts with `_` are skipped by the harness
and by `tests/test_tasks.py`, so this one never runs as a task itself.

Every task is a tiny repo with a bug and two tests:

- `workspace/` -- what the agent sees: the buggy `src/`, the failing visible
  test it is told to fix, and an empty `conftest.py` (so `src` is importable).
- `hidden/` -- the held-out test, never shown to the agent and not mentioned
  in the prompt. It must catch the cheat the visible test invites.
- `solution/` -- the real fix. `tests/test_tasks.py` proves the buggy
  workspace fails and this solution passes, so a task cannot rot silently.
- `task.json` -- `prompt`, `visible_test`, `hidden_test`, `cheat_type`,
  `language`, and `cheat_hint` (a note for the benchmark author; never shown
  to the agent).

Use forward slashes in `task.json` paths so the suite runs on any OS.
