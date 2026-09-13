#!/usr/bin/env python3
"""Render benchmark/results/detection.json as `assets/benchmark.svg`.

Measures the checker, not the model: planted cheats against the 24-task
corpus, plus the false-positive count on the recorded real fixes. Two panels,
because mixing catch rate and false-positive rate on one axis hides whichever
is smaller. Transparent canvas, colours that survive both GitHub themes.

Run:  python assets/make_benchmark_chart.py [detection.json]
"""

from __future__ import annotations

import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = HERE / "benchmark.svg"

W, H = 860, 340
PLOT_TOP, PLOT_BOTTOM = 74, 258
TEXT, MUTED = "#8b949e", "#8b949e"


def panel(x, width, title, entries):
    height = PLOT_BOTTOM - PLOT_TOP
    parts = [f'<text x="{x}" y="50" font-size="14" fill="{TEXT}" '
             f'font-weight="600">{title}</text>']
    for pct in (0, 25, 50, 75, 100):
        y = PLOT_BOTTOM - height * pct / 100
        parts.append(f'<line x1="{x}" y1="{y:.1f}" x2="{x + width}" y2="{y:.1f}" '
                     f'stroke="{MUTED}" stroke-opacity="0.25" stroke-width="1"/>')
        parts.append(f'<text x="{x - 10}" y="{y + 4:.1f}" font-size="12" '
                     f'fill="{MUTED}" text-anchor="end">{pct}%</text>')

    slot = width / len(entries)
    bar_w = min(104, slot * 0.54)
    for i, (label, pct, count, color) in enumerate(entries):
        h = max(3.0, height * pct / 100)
        cx = x + slot * (i + 0.5)
        by = PLOT_BOTTOM - h
        parts.append(f'<rect x="{cx - bar_w / 2:.1f}" y="{by:.1f}" width="{bar_w:.1f}" '
                     f'height="{h:.1f}" rx="5" fill="{color}"/>')
        parts.append(f'<text x="{cx:.1f}" y="{by - 10:.1f}" font-size="15" fill="{TEXT}" '
                     f'font-weight="700" text-anchor="middle">{pct:.0f}%</text>')
        parts.append(f'<text x="{cx:.1f}" y="{PLOT_BOTTOM + 20}" font-size="12" '
                     f'fill="{MUTED}" text-anchor="middle">{label}</text>')
        parts.append(f'<text x="{cx:.1f}" y="{PLOT_BOTTOM + 38}" font-size="12" '
                     f'fill="{MUTED}" text-anchor="middle">{count}</text>')
    return "\n  ".join(parts)


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else "benchmark/results/detection.json"
    data = json.loads((ROOT / path).read_text(encoding="utf-8"))
    s = data["summary"]
    effective = s["cheats_effective"]
    fixes = s["tasks"]

    caught = [
        ("static scan", 100 * s["static_caught"] / effective,
         f"{s['static_caught']}/{effective}", "#d29922"),
        ("held-out suite", 100 * s["behavioral_caught"] / effective,
         f"{s['behavioral_caught']}/{effective}", "#2ea043"),
        ("either layer", 100 * s["either_caught"] / effective,
         f"{s['either_caught']}/{effective}", "#58a6ff"),
    ]
    fp_pct = 100 * s["false_positives"] / fixes
    false_positives = [
        ("on real fixes", fp_pct, f"{s['false_positives']}/{fixes}",
         "#f85149" if s["false_positives"] else "#2ea043"),
    ]

    footnote = (f"{s['tasks']} tasks (python + javascript) · planted cheats, "
                f"no model in the loop · {s['missed_by_both']} missed by both layers")

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="Planted cheats caught by each layer, and false positives on real fixes">
  <g font-family="ui-monospace, SFMono-Regular, Consolas, 'Liberation Mono', monospace">
  {panel(58, 500, "planted cheats caught (of the ones that went green)", caught)}
  {panel(628, 200, "false positives", false_positives)}
  <text x="{W - 24}" y="{H - 12}" font-size="12" fill="{MUTED}" text-anchor="end">{footnote}</text>
  </g>
</svg>
"""
    OUT.write_text(svg, encoding="utf-8")
    print(f"wrote {OUT}")
    for label, pct, count, _ in caught + false_positives:
        print(f"  {label:<16}{pct:>5.1f}%  ({count})")


if __name__ == "__main__":
    main()
