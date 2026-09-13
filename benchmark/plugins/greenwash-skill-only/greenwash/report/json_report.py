"""The versioned JSON wire format.

This is the contract other tools read. `schema_version` is the first key, and
`TrustReport.to_dict()` guarantees a field is present (with a default) rather
than absent, so a consumer never has to guess.
"""

from __future__ import annotations

import json

from ..domain import TrustReport


def render(report: TrustReport, indent: int = 2) -> str:
    return json.dumps(report.to_dict(), indent=indent, sort_keys=False) + "\n"
