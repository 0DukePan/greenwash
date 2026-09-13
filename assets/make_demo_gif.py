#!/usr/bin/env python3
"""Build `assets/demo.gif` -- the real output of `python demo/run_demo.py`,
typed onto a terminal card.

Nothing here is a mock-up: the lines come from running the demo and capturing
its stdout, so the GIF cannot drift from what the command actually prints.
The flag lines are highlighted for readability; the text itself is verbatim.

Frames are drawn at 2x and downsampled, so text and corners are antialiased.
The clip opens on the payoff (the fully caught state) so the poster frame
GitHub and social previews grab is the catch, not an empty terminal, and it
loops back onto that same frame.

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
W, H = 720, 550          # final canvas
INSET = 16               # card distance from the canvas edge
RADIUS = 12
HEADER = 26              # terminal chrome strip
TEXT_LEFT = 38
TEXT_TOP = 54
LINE_H = 22
SIZE = 16

BG = (9, 12, 17)
CARD, BORDER, DIVIDER = (14, 18, 24), (31, 38, 47), (26, 32, 40)
DOTS = [(255, 95, 86), (255, 189, 46), (39, 201, 63)]
PROMPT, CMD = (63, 185, 80), (230, 237, 243)
BODY, FLAG, DIM = (201, 209, 217), (240, 136, 62), (139, 148, 158)

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
        [x0, y0 + px(8), x1, y1 + px(10)], radius=px(RADIUS + 2), fill=110)
    img.paste(Image.new("RGB", img.size, (0, 0, 0)), (0, 0),
              shadow.filter(ImageFilter.GaussianBlur(px(7))))

    d = ImageDraw.Draw(img)
    d.rounded_rectangle([x0, y0, x1, y1], radius=px(RADIUS), fill=CARD,
                        outline=BORDER, width=px(1))
    d.line([x0 + px(1), y0 + px(HEADER), x1 - px(1), y0 + px(HEADER)],
           fill=DIVIDER, width=px(1))
    for i, color in enumerate(DOTS):
        cx, cy = x0 + px(16 + 15 * i), y0 + px(13)
        d.ellipse([cx - px(4.5), cy - px(4.5), cx + px(4.5), cy + px(4.5)], fill=color)
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
        elif kind == "flag":
            end = line.index("]") + 1
            d.text((px(TEXT_LEFT), y), line[:end], font=FONT, fill=FLAG)
            x = TEXT_LEFT + d.textlength(line[:end], font=FONT) / S
            d.text((px(x), y), line[end:], font=FONT, fill=CMD)
        else:
            fill = {"out": BODY, "dim": DIM}[kind]
            d.text((px(TEXT_LEFT), y), line, font=FONT, fill=fill)
    if cursor is not None:
        y = px(TEXT_TOP + cursor * LINE_H)
        d.rectangle([px(TEXT_LEFT), y - px(1), px(TEXT_LEFT + 9), y + px(17)], fill=CMD)
    return img


def story_frames():
    """The demo, in order: narration already visible, two commands, two flags."""
    lines = demo_lines()
    kinds = classify(lines)
    commands = [i for i, line in enumerate(lines) if line.startswith("$ ")]
    frames: list[tuple[Image.Image, int]] = []

    def add(visible, ms, cursor=None):
        frames.append((render(visible, cursor), ms))

    visible = [(lines[i], kinds[i]) for i in range(commands[0])]
    add(visible, 420, cursor=len(visible))

    for k, start in enumerate(commands):
        end = commands[k + 1] if k + 1 < len(commands) else len(lines)
        command = lines[start]
        step = 2 if len(command) <= 20 else 5         # long commands paste faster
        for n in range(step, len(command), step):
            add(visible + [(command[:n], "cmd")], 35, cursor=len(visible))
        add(visible + [(command, "cmd")], 70, cursor=len(visible))
        visible.append((command, "cmd"))
        add(visible, 240)
        for i in range(start + 1, end):               # this command's output
            visible.append((lines[i], kinds[i]))
            add(visible, 40 if not lines[i].strip() else 110)
        add(visible, 1100 if k == 0 else 900)         # let the catch land
    return frames


def build():
    story = story_frames()
    poster = story[-1][0]
    opening = story[0][0]

    frames = [(poster, 900)]                          # poster frame = the catch
    for t in (0.4, 0.75, 1.0):                        # dissolve into the story
        frames.append((Image.blend(poster, opening, t), 90))
    frames.extend(story)                              # ends on the same poster
    return frames


def main() -> None:
    frames = build()

    preview = None
    if "--preview" in sys.argv:
        preview = pathlib.Path(sys.argv[sys.argv.index("--preview") + 1])
        preview.mkdir(parents=True, exist_ok=True)

    paletted = []
    for i, (img, _) in enumerate(frames):
        final = img.resize((W, H), Image.LANCZOS)
        if preview is not None and i % max(1, len(frames) // 12) == 0:
            final.save(preview / f"frame-{i:03d}.png")
        paletted.append(final.convert("P", palette=Image.ADAPTIVE, colors=32))

    paletted[0].save(OUT, save_all=True, append_images=paletted[1:],
                     duration=[ms for _, ms in frames], loop=0, optimize=True,
                     disposal=2)
    print(f"wrote {OUT} -- {len(frames)} frames, {W}x{H}, "
          f"{OUT.stat().st_size / 1024:.0f} KB, "
          f"{sum(ms for _, ms in frames) / 1000:.1f}s loop")


if __name__ == "__main__":
    main()
