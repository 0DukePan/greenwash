"""Flag record and output rendering."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass


@dataclass
class Flag:
    file: str
    kind: str
    detail: str


def render_json(flags, verification=None) -> str:
    out = {"clean": not flags, "flags": [asdict(f) for f in flags]}
    if verification is not None:
        out["verification"] = verification
    return json.dumps(out, indent=2)


def render_text(flags, verification=None) -> str:
    lines = []
    if verification is not None:
        summary = ", ".join(
            f"{k}={'pass' if ok else 'fail'}" for k, ok in verification.items()
        )
        lines.append(f"greenwash: verification -- {summary}")
    if not flags:
        lines.append("greenwash: clean -- nothing here fakes a passing suite.")
        return "\n".join(lines)
    lines.append(f"greenwash: {len(flags)} flag(s) -- explain these before calling it done.")
    lines.append("")
    for f in flags:
        lines.append(f"  [{f.kind}] {f.file}")
        lines.append(f"      {f.detail}")
    return "\n".join(lines)
