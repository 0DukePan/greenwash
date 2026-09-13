#!/usr/bin/env python3
"""Render benchmark/results/detection.json as `assets/benchmark.svg`.

Grouped bars: for each cheat type the corpus tempts, how often the static scan
and the held-out suite caught it. The false-positive panel is separate so a
zero cannot be mistaken for a bar that failed to draw. Transparent canvas,
colours that survive both GitHub themes.

Run:  python assets/make_benchmark_chart.py [detection.json]
"""

from __future__ import annotations

import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = HERE / "benchmark.svg"

W, H = 860, 360
PLOT_TOP, PLOT_BOTTOM = 96, 268
TEXT, MUTED = "#8b949e", "#8b949e"
STATIC, BEHAVIORAL = "#d29922", "#2ea043"


def bars(entries):
    parts = []
    for pct in (0, 25, 50, 75, 100):
        y = PLOT_BOTTOM - (PLOT_BOTTOM - PLOT_TOP) * pct / 100
        parts.append(f'<line x1="58" y1="{y:.1f}" x2="646" y2="{y:.1f}" '
                     f'stroke="{MUTED}" stroke-opacity="0.25" stroke-width="1"/>')
        parts.append(f'<text x="48" y="{y + 4:.1f}" font-size="12" fill="{MUTED}" '
                     f'text-anchor="end">{pct}%</text>')

    slot = (646 - 58) / len(entries)
    for i, (kind, cell) in enumerate(entries):
        cx = 58 + slot * (i + 0.5)
        for j, (key, color) in enumerate((("static_caught", STATIC),
                                          ("behavioral_caught", BEHAVIORAL))):
            total = cell["effective"] or 1
            pct = 100 * cell[key] / total
            h = max(3.0, (PLOT_BOTTOM - PLOT_TOP) * pct / 100)
            x = cx - 34 + j * 38
            parts.append(f'<rect x="{x:.1f}" y="{PLOT_BOTTOM - h:.1f}" width="30" '
                         f'height="{h:.1f}" rx="4" fill="{color}"/>')
            parts.append(f'<text x="{x + 15:.1f}" y="{PLOT_BOTTOM - h - 7:.1f}" '
                         f'font-size="11" fill="{MUTED}" text-anchor="middle">'
                         f'{cell[key]}/{cell["effective"]}</text>')
        parts.append(f'<text x="{cx:.1f}" y="{PLOT_BOTTOM + 20}" font-size="12" '
                     f'fill="{MUTED}" text-anchor="middle">{kind}</text>')
    return "\n  ".join(parts)


def fp_panel(x, width, count, total):
    pct = 100 * count / total if total else 0.0
    h = max(3.0, (PLOT_BOTTOM - PLOT_TOP) * pct / 100) if pct else 3.0
    color = "#f85149" if count else BEHAVIORAL
    return "\n  ".join([
        f'<line x1="{x}" y1="{PLOT_BOTTOM}" x2="{x + width}" y2="{PLOT_BOTTOM}" '
        f'stroke="{MUTED}" stroke-opacity="0.25" stroke-width="1"/>',
        f'<rect x="{x + width / 2 - 26:.1f}" y="{PLOT_BOTTOM - h:.1f}" width="52" '
        f'height="{h:.1f}" rx="4" fill="{color}"/>',
        f'<text x="{x + width / 2:.1f}" y="{PLOT_BOTTOM - h - 9:.1f}" font-size="14" '
        f'fill="{TEXT}" font-weight="700" text-anchor="middle">{pct:.0f}%</text>',
        f'<text x="{x + width / 2:.1f}" y="{PLOT_BOTTOM + 20}" font-size="12" '
        f'fill="{MUTED}" text-anchor="middle">{count}/{total} real fixes</text>',
    ])


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else "benchmark/results/detection.json"
    data = json.loads((ROOT / path).read_text(encoding="utf-8"))
    s = data["summary"]
    by_type = sorted(s["by_cheat_type"].items())
    by_type.sort(key=lambda kv: -kv[1]["effective"])

    footnote = (f"{s['tasks']} tasks (python + javascript) · each attacked with the "
                f"cheat it tempts · no model in the loop")
    legend = (f'<rect x="58" y="64" width="12" height="12" rx="3" fill="{STATIC}"/>'
              f'<text x="76" y="74" font-size="12" fill="{MUTED}">static scan</text>'
              f'<rect x="166" y="64" width="12" height="12" rx="3" fill="{BEHAVIORAL}"/>'
              f'<text x="184" y="74" font-size="12" fill="{MUTED}">held-out suite</text>'
              f'<text x="58" y="44" font-size="14" fill="{TEXT}" font-weight="600">'
              f'planted cheats caught, by cheat type</text>'
              f'<text x="740" y="44" font-size="14" fill="{TEXT}" font-weight="600">'
              f'false positives</text>')

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="Planted cheats caught by the static scan and the held-out suite, per cheat type, and the false-positive count on real fixes">
  <g font-family="ui-monospace, SFMono-Regular, Consolas, 'Liberation Mono', monospace">
  {legend}
  {bars(by_type)}
  {fp_panel(700, 120, s["false_positives"], s["tasks"])}
  <text x="{W - 24}" y="{H - 12}" font-size="12" fill="{MUTED}" text-anchor="end">{footnote}</text>
  </g>
</svg>
"""
    OUT.write_text(svg, encoding="utf-8")
    print(f"wrote {OUT}")
    for kind, cell in by_type:
        print(f"  {kind:<10} static {cell['static_caught']}/{cell['effective']}  "
              f"behavioral {cell['behavioral_caught']}/{cell['effective']}")


if __name__ == "__main__":
    main()
