"""`conftest.py` was touched.

Fixture and hook patching here reaches every test in the tree, which makes it
the highest-leverage file in a Python suite and a documented exploit surface.
Most conftest edits are ordinary fixture work, so this asks rather than accuses.
"""

from __future__ import annotations

import os

from .base import TEST_INTEGRITY, Rule

RULE = Rule(
    id="conftest-changed",
    code="GW-TEST-006",
    title="conftest.py changed",
    category=TEST_INTEGRITY,
    severity="MEDIUM",
    confidence="LOW",
    description="conftest.py changed -- fixtures and hooks here apply repo-wide.",
    remediation="Confirm the change does not mask failures for other tests.",
    requires_review=True,
)


def check(ctx) -> list:
    return [RULE.signal(path, None, "conftest.py changed -- fixture or hook changes here "
                                    "can mask failures repo-wide")
            for path in [*ctx.paths(), *ctx.deleted]
            if os.path.basename(path) == "conftest.py"]
