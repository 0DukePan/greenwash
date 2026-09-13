#!/usr/bin/env python3
"""Build `assets/demo.gif` -- the real output of `python demo/run_demo.py`,
typed onto a dark terminal card.

Nothing here is a mock-up: the lines come from running the demo and capturing
its stdout, so the GIF cannot drift from what the command actually prints. The
2x supersampled frames are downsampled and quantized to a small palette.

Needs Pillow and a monospace font (Consolas, Cascadia Mono, DejaVu Sans Mono).

Run:  python assets/make_demo_gif.py [--preview DIR]
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = HERE / "demo.gif"

S = 2                    # supersampling factor
W, H = 720, 560          # final canvas
INSET = 20               # card distance from the canvas edge
RADIUS = 13
TEXT_LEFT = 44
TEXT_TOP = 42
LINE_H = 22
SIZE = 15

BG = (9, 12, 17)
CARD, BORDER = (14, 18, 24), (31, 38, 47)
PROMPT, CMD = (63, 185, 80), (230, 237, 243)
BODY, FLAG, DIM = (201, 209, 217), (230, 237, 243), (139, 148, 158)
COLORS = {"out": BODY, "flag": FLAG, "dim": DIM}

FONT_DIRS = [
    pathlib.Path(r"C:\Windows\Fonts"),
    pathlib.Path("/usr/share/fonts/truetype/dejavu"),
    pathlib.Path("/usr/share/fonts/truetype/liberation"),
    pathlib.Path("/System/Library/Fonts"),
    pathlib.Path("/Library/Fonts"),
]
FONT_FILES = {
    "regular": ["consola.ttf", "CascadiaMono.ttf", "DejaVuSansMono.ttf", "Menlo.ttc"],
    "bold": ["consolab.ttf", "CascadiaMono-Bold.ttf", "DejaVuSansMono-Bold.ttf"],
}


def font(style: str):
    for directory in FONT_DIRS:
        for name in FONT_FILES[style]:
            path = directory / name
            if path.is_file():
                return ImageFont.truetype(str(path), SIZE * S)
    return ImageFont.load_default()


FONT, FONT_BOLD = font("regular"), font("bold")


def px(v: float) -> int:
    return int(round(v * S))


def demo_lines() -> list[str]:
    proc = subprocess.run([sys.executable, str(ROOT / "demo" / "run_demo.py")],
                          capture_output=True, text=True, cwd=ROOT)
    if proc.returncode != 0:
        sys.exit(f"demo/run_demo.py failed:\n{proc.stderr}")
    return [line.rstrip() for line in proc.stdout.splitlines()]


def classify(lines: list[str]) -> list[str]:
    first = next(i for i, line in enumerate(lines) if line.startswith("$ "))
    kinds = []
    for i, line in enumerate(lines):
        if i < first:
            kinds.append("dim")
        elif line.startswith("$ "):
            kinds.append("cmd")
        elif line.lstrip().startswith("["):
            kinds.append("flag")
        elif line.startswith("      "):
            kinds.append("dim")
        else:
            kinds.append("out")
    return kinds


def card() -> Image.Image:
    img = Image.new("RGB", (W * S, H * S), BG)
    x0, y0 = px(INSET), px(INSET)
    x1, y1 = px(W - INSET), px(H - INSET)

    shadow = Image.new("L", img.size, 0)
    ImageDraw.Draw(shadow).rounded_rectangle(
        [x0, y0 + px(10), x1, y1 + px(12)], radius=px(RADIUS + 2), fill=110)
    img.paste(Image.new("RGB", img.size, (0, 0, 0)), (0, 0),
              shadow.filter(ImageFilter.GaussianBlur(px(8))))

    d = ImageDraw.Draw(img)
    d.rounded_rectangle([x0, y0, x1, y1], radius=px(RADIUS), fill=CARD,
                        outline=BORDER, width=px(1))
    return img


BASE = card()


def render(visible, cursor=None) -> Image.Image:
    img = BASE.copy()
    d = ImageDraw.Draw(img)
    for row, (line, kind) in enumerate(visible):
        y = px(TEXT_TOP + row * LINE_H)
        if kind == "cmd":
            d.text((px(TEXT_LEFT), y), "$", font=FONT_BOLD, fill=PROMPT)
            x = TEXT_LEFT + d.textlength("$ ", font=FONT_BOLD) / S
            d.text((px(x), y), line[2:], font=FONT, fill=CMD)
        else:
            d.text((px(TEXT_LEFT), y), line, font=FONT, fill=COLORS[kind])
    if cursor is not None:
        y = px(TEXT_TOP + cursor * LINE_H)
        d.rectangle([px(TEXT_LEFT), y - px(1), px(TEXT_LEFT + 9), y + px(18)], fill=CMD)
    return img


def build():
    lines = demo_lines()
    kinds = classify(lines)
    commands = [i for i, line in enumerate(lines) if line.startswith("$ ")]
    frames: list[tuple[Image.Image, int]] = []

    def add(visible, ms, cursor=None):
        frames.append((render(visible, cursor), ms))

    visible: list[tuple[str, str]] = []
    add(visible, 320, cursor=0)

    for i in range(commands[0]):                      # the setup narration
        visible.append((lines[i], kinds[i]))
    add(visible, 320)

    for k, start in enumerate(commands):
        end = commands[k + 1] if k + 1 < len(commands) else len(lines)
        command = lines[start]
        step = 2 if len(command) <= 20 else 5         # long commands paste faster
        for n in range(step, len(command), step):
            add(visible + [(command[:n], "cmd")], 35, cursor=len(visible))
        add(visible + [(command, "cmd")], 70, cursor=len(visible))
        visible.append((command, "cmd"))
        add(visible, 260)
        for i in range(start + 1, end):               # this command's output
            visible.append((lines[i], kinds[i]))
            add(visible, 40 if not lines[i].strip() else 115)
        add(visible, 450)

    add(visible, 2200)
    for _ in range(3):                                # waiting cursor, as a shell
        add(visible, 200, cursor=len(visible))
        add(visible, 200)

    last = frames[-1][0]
    for t in (0.35, 0.7, 1.0):                        # dissolve back to the start
        frames.append((Image.blend(last, BASE, t), 100))
    return frames


def main() -> None:
    frames = build()

    preview = None
    if "--preview" in sys.argv:
        preview = pathlib.Path(sys.argv[sys.argv.index("--preview") + 1])
        preview.mkdir(parents=True, exist_ok=True)

    paletted = []
    for i, (img, _) in enumerate(frames):
        if preview is not None and i % max(1, len(frames) // 12) == 0:
            img.save(preview / f"frame-{i:03d}.png")
        paletted.append(img.convert("P", palette=Image.ADAPTIVE, colors=32))

    paletted[0].save(OUT, save_all=True, append_images=paletted[1:],
                     duration=[ms for _, ms in frames], loop=0, optimize=True,
                     disposal=2)
    print(f"wrote {OUT} -- {len(frames)} frames, "
          f"{OUT.stat().st_size / 1024:.0f} KB, "
          f"{sum(ms for _, ms in frames) / 1000:.1f}s loop")


if __name__ == "__main__":
    main()
