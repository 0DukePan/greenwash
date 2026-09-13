#!/usr/bin/env python3
"""Build `assets/demo.gif` -- the real output of `python demo/run_demo.py
--terse`, typed onto a terminal card.

Nothing here is a mock-up: the generator runs the demo and captures its stdout,
so the GIF cannot drift from what the command prints. The only styling it adds
is the tint and amber tag on the flag lines; the text is verbatim. The two-line
kicker above the terminal is the one thing that is not output -- it is there so
the clip reads as a catch without needing its caption.

The clip opens on the caught state, so the poster frame GitHub and social
previews grab is the catch rather than an empty terminal, and it loops back
onto that same frame.

Frames are drawn at 2x and downsampled. Needs Pillow and a monospace font
(Consolas, Cascadia Mono, DejaVu Sans Mono).

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
W, H = 768, 482          # final canvas
INSET = 14               # card distance from the canvas edge
CARD_TOP = 76            # room above the card for the kicker
RADIUS = 12
HEADER = 26              # terminal chrome strip
TEXT_LEFT = 34
TEXT_TOP = CARD_TOP + 36
LINE_H = 25
SIZE = 17

BG = (9, 12, 17)
CARD, BORDER, DIVIDER = (14, 18, 24), (31, 38, 47), (26, 32, 40)
DOTS = [(255, 95, 86), (255, 189, 46), (39, 201, 63)]
PROMPT, CMD = (63, 185, 80), (230, 237, 243)
BODY, FLAG, DIM = (201, 209, 217), (240, 136, 62), (139, 148, 158)
FLASH = (255, 176, 104)  # the tag's first 140ms, so the catch registers
TINT = (35, 29, 24)      # card colour, warmed up: the flag-row highlight

# Above the card: two lines of framing, so the clip reads without its caption.
KICKER = [('An agent "fixed" the failing test.', SIZE, CMD),
          ("It hardcoded the answer.", SIZE - 2, DIM)]
KICKER_TOP, KICKER_L1, KICKER_L2, KICKER_X = 18, 24, 22, INSET + 6

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


def font(style: str, size: int = SIZE):
    for directory in FONT_DIRS:
        for name in FONT_FILES[style]:
            path = directory / name
            if path.is_file():
                return ImageFont.truetype(str(path), size * S)
    return ImageFont.load_default()


FONT, FONT_BOLD = font("regular"), font("bold")


def px(v: float) -> int:
    return int(round(v * S))


def demo_lines() -> list[str]:
    proc = subprocess.run([sys.executable, str(ROOT / "demo" / "run_demo.py"),
                           "--terse"],
                          capture_output=True, text=True, cwd=ROOT)
    if proc.returncode != 0:
        sys.exit(f"demo/run_demo.py --terse failed:\n{proc.stderr}")
    return [line.rstrip() for line in proc.stdout.splitlines()]


def classify(lines: list[str]) -> list[str]:
    kinds = []
    for line in lines:
        if line.startswith("$ "):
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
    x0, y0 = px(INSET), px(CARD_TOP)
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

    y = px(KICKER_TOP)
    for text, size, color in KICKER:
        d.text((px(KICKER_X), y), text, font=font("regular", size), fill=color)
        y += px(KICKER_L1 if size == SIZE else KICKER_L2)
    return img


BASE = card()


def runs(rows) -> list[list[int]]:
    """Contiguous runs of row indices, so a flagged block gets one edge."""
    out: list[list[int]] = []
    for row in sorted(rows):
        if out and row == out[-1][-1] + 1:
            out[-1].append(row)
        else:
            out.append([row])
    return out


def render(visible, cursor=None, flash=()) -> Image.Image:
    img = BASE.copy()
    d = ImageDraw.Draw(img)

    # tint every flag line and the detail lines under it, as one block
    tinted, i = set(), 0
    while i < len(visible):
        if visible[i][1] == "flag":
            tinted.add(i)
            j = i + 1
            while j < len(visible) and visible[j][1] == "dim":
                tinted.add(j)
                j += 1
            i = j
        else:
            i += 1

    for row in tinted:
        y = px(TEXT_TOP + row * LINE_H)
        d.rectangle([px(INSET + 5), y - px(3), px(W - INSET - 5), y + px(20)], fill=TINT)
    for run in runs(tinted):
        y0 = px(TEXT_TOP + run[0] * LINE_H) - px(3)
        y1 = px(TEXT_TOP + run[-1] * LINE_H) + px(20)
        edge = FLASH if run[0] in flash else FLAG
        d.rectangle([px(INSET + 5), y0, px(INSET + 8), y1], fill=edge)

    for row, (line, kind) in enumerate(visible):
        y = px(TEXT_TOP + row * LINE_H)
        if kind == "cmd":
            d.text((px(TEXT_LEFT), y), "$", font=FONT_BOLD, fill=PROMPT)
            x = TEXT_LEFT + d.textlength("$ ", font=FONT_BOLD) / S
            d.text((px(x), y), line[2:], font=FONT, fill=CMD)
        elif kind == "flag":
            end = line.index("]") + 1
            tag = FLASH if row in flash else FLAG
            d.text((px(TEXT_LEFT), y), line[:end], font=FONT, fill=tag)
            x = TEXT_LEFT + d.textlength(line[:end], font=FONT) / S
            d.text((px(x), y), line[end:], font=FONT, fill=CMD)
        else:
            d.text((px(TEXT_LEFT), y), line, font=FONT,
                   fill={"out": BODY, "dim": DIM}[kind])
    if cursor is not None:
        y = px(TEXT_TOP + cursor * LINE_H)
        d.rectangle([px(TEXT_LEFT), y - px(1), px(TEXT_LEFT + 9), y + px(18)], fill=CMD)
    return img


def story_frames():
    """The demo, in order: two commands, their output, the flags."""
    lines = demo_lines()
    kinds = classify(lines)
    commands = [i for i, line in enumerate(lines) if line.startswith("$ ")]
    frames: list[tuple[Image.Image, int]] = []
    visible: list[tuple[str, str]] = []

    def add(ms, cursor=None):
        frames.append((render(visible, cursor), ms))

    add(260, cursor=0)

    for k, start in enumerate(commands):
        end = commands[k + 1] if k + 1 < len(commands) else len(lines)
        command = lines[start]
        step = 2 if len(command) <= 20 else 8         # long commands paste faster
        for n in range(step, len(command), step):
            frames.append((render(visible + [(command[:n], "cmd")], len(visible)), 45))
        frames.append((render(visible + [(command, "cmd")], len(visible)), 90))
        visible.append((command, "cmd"))
        add(200)
        for i in range(start + 1, end):               # this command's output
            visible.append((lines[i], kinds[i]))
            if kinds[i] == "flag":                    # pulse, then settle
                row = len(visible) - 1
                for ms in (70, 70):
                    frames.append((render(visible, None, flash={row}), ms))
            add(45 if not lines[i].strip() else (135 if kinds[i] != "dim" else 120))
        add(1000 if k == 0 else 1500)                 # let the catch land
    return frames


def build():
    story = story_frames()
    poster = story[-1][0]
    opening = story[0][0]

    frames = [(poster, 700)]                          # poster frame = the catch
    for t in (0.4, 0.75, 1.0):                        # dissolve into the story
        frames.append((Image.blend(poster, opening, t), 70))
    frames.extend(story)                              # ends on the same poster
    return frames


ACCENTS = [BG, CARD, TINT, BORDER, DIVIDER, CMD, BODY, DIM, FLAG, PROMPT, *DOTS]


def palette(frames) -> Image.Image:
    """Palette from the art's own colours, with the accents forced in.

    Adaptive quantisation quietly dropped the green `$`: it is a few dozen
    pixels against a frame of greys, so median cut never spends a slot on it.
    """
    counts: dict[tuple, int] = {}
    step = max(1, len(frames) // 8)
    for img in frames[::step]:
        for n, color in img.getcolors(1 << 22):
            counts[color] = counts.get(color, 0) + n

    colors = [c for c, _ in sorted(counts.items(), key=lambda kv: -kv[1])][:96]
    for accent in ACCENTS:
        if all(sum((a - b) ** 2 for a, b in zip(accent, c)) > 144 for c in colors):
            colors.append(accent)

    pal = Image.new("P", (1, 1))
    pal.putpalette([v for c in colors[:256] for v in c]
                   + [0] * (768 - 3 * len(colors[:256])))
    return pal


def main() -> None:
    frames = build()

    preview = None
    if "--preview" in sys.argv:
        preview = pathlib.Path(sys.argv[sys.argv.index("--preview") + 1])
        preview.mkdir(parents=True, exist_ok=True)

    flats = [img.resize((W, H), Image.LANCZOS) for img, _ in frames]
    pal = palette(flats)

    paletted = []
    for i, img in enumerate(flats):
        if preview is not None and i % max(1, len(frames) // 12) == 0:
            img.save(preview / f"frame-{i:03d}.png")
        paletted.append(img.quantize(palette=pal, dither=Image.Dither.NONE))

    paletted[0].save(OUT, save_all=True, append_images=paletted[1:],
                     duration=[ms for _, ms in frames], loop=0, optimize=True,
                     disposal=2)
    print(f"wrote {OUT} -- {len(frames)} frames, {W}x{H}, "
          f"{OUT.stat().st_size / 1024:.0f} KB, "
          f"{sum(ms for _, ms in frames) / 1000:.1f}s loop")


if __name__ == "__main__":
    main()
