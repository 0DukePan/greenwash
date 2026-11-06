"""Suite-wide isolation for state that would otherwise outlive a run.

The Stop hook's block budget is resolved through git: a target directory that
is not itself a repository inherits the state of whichever ancestor repository
it sits under. On this machine every pytest temp directory sits under the
user's home, and the home directory is itself a repository -- so every test
shared one budget across runs, and running the suite a second time failed the
strict-gate tests with an already-exhausted budget.

A per-session directory makes the suite idempotent. `hooking._state_path`
honours `GREENWASH_STATE_DIR`, and every hook subprocess inherits it through
the environment.
"""

import os
import tempfile

import pytest


@pytest.fixture(scope="session", autouse=True)
def isolated_hook_state():
    """Point the hook's block budget at a directory that dies with this run."""
    previous = os.environ.get("GREENWASH_STATE_DIR")
    state_dir = tempfile.mkdtemp(prefix="greenwash-hook-state-")
    os.environ["GREENWASH_STATE_DIR"] = state_dir
    try:
        yield state_dir
    finally:
        if previous is None:
            os.environ.pop("GREENWASH_STATE_DIR", None)
        else:
            os.environ["GREENWASH_STATE_DIR"] = previous
