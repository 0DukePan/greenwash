#!/usr/bin/env python3
"""Build `assets/demo.gif` -- the real output of `python demo/run_demo.py
--terse`, typed onto a terminal card that scrolls.

Nothing here is a mock-up: the generator runs the demo and captures its stdout,
so the GIF cannot drift from what the command prints. The only styling it adds
is the tint and amber tag on the signal lines; the text is verbatim. The
two-line kicker above the terminal is the one thing that is not output -- it is
there so the clip reads as a catch without needing its caption.

The report is taller than the window, so the viewport follows the newest line
the way a real terminal does, and the clip settles on the verdict. That last
frame is also the first, so the loop is seamless and GitHub's poster frame is
the punchline rather than a mostly-empty screen.

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
W, H = 768, 486          # final canvas
INSET = 14               # card distance from the canvas edge
CARD_TOP = 78            # room above the card for the kicker
RADIUS = 12
HEADER = 26              # terminal chrome strip
TEXT_LEFT = 30
TEXT_TOP = CARD_TOP + 36
LINE_H = 23
SIZE = 16

BG = (9, 12, 17)
CARD, BORDER, DIVIDER = (14, 18, 24), (31, 38, 47), (26, 32, 40)
DOTS = [(255, 95, 86), (255, 189, 46), (39, 201, 63)]
PROMPT, CMD = (63, 185, 80), (230, 237, 243)
BODY, FLAG, DIM = (201, 209, 217), (240, 136, 62), (139, 148, 158)
FLASH = (255, 176, 104)   # the tag's first 140ms, so the catch registers
ALERT, VERDICT_BAD = (255, 123, 114), (255, 123, 114)
TINT = (35, 29, 24)       # card colour, warmed up: the signal-row highlight

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


def font(style: str, size: float = SIZE):
    for directory in FONT_DIRS:
        for name in FONT_FILES[style]:
            path = directory / name
            if path.is_file():
                return ImageFont.truetype(str(path), int(size * S))
    return ImageFont.load_default()


FONT, FONT_BOLD = font("regular"), font("bold")


def px(value: float) -> int:
    return int(round(value * S))


def demo_lines() -> list:
    proc = subprocess.run([sys.executable, str(ROOT / "demo" / "run_demo.py"), "--terse"],
                          capture_output=True, text=True, cwd=ROOT)
    if proc.returncode != 0:
        sys.exit(f"demo/run_demo.py --terse failed:\n{proc.stderr}")
    return [line.rstrip() for line in proc.stdout.splitlines()]


def classify(line: str) -> str:
    stripped = line.strip()
    if line.startswith("$ ") or line.startswith("      --"):
        return "cmd"
    if stripped.startswith("! ["):
        return "signal"
    if stripped.startswith("x "):
        return "fail"
    if stripped.startswith("Verdict:"):
        return "verdict"
    if stripped.startswith(("Confidence:", "+ ", "- ")):
        return "check"
    if line.startswith(" ") or (not stripped[:1].isalnum() and stripped):
        return "dim"
    return "out"


def rows_visible() -> int:
    return max(1, ((H - INSET) - (TEXT_TOP + 12)) // LINE_H)


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
    for index, colour in enumerate(DOTS):
        cx, cy = x0 + px(16 + 15 * index), y0 + px(13)
        d.ellipse([cx - px(4.5), cy - px(4.5), cx + px(4.5), cy + px(4.5)], fill=colour)

    y = px(KICKER_TOP)
    for text, size, colour in KICKER:
        d.text((px(KICKER_X), y), text, font=font("regular", size), fill=colour)
        y += px(KICKER_L1 if size == SIZE else KICKER_L2)
    return img


BASE = card()
VISIBLE = rows_visible()


def runs(rows) -> list:
    """Contiguous runs of row indices, so a flagged block gets one edge."""
    out: list = []
    for row in sorted(rows):
        if out and row == out[-1][-1] + 1:
            out[-1].append(row)
        else:
            out.append([row])
    return out


def signal_blocks(visible) -> set:
    """Signal lines plus the indented detail lines under them."""
    tinted, index = set(), 0
    while index < len(visible):
        if visible[index][1] == "signal":
            tinted.add(index)
            follower = index + 1
            while follower < len(visible) and visible[follower][1] == "dim":
                tinted.add(follower)
                follower += 1
            index = follower
        else:
            index += 1
    return tinted


def scroll_for(rows: int) -> int:
    return max(0, rows - VISIBLE)


def render(visible, scroll: int = None, flash=(), cursor: bool = False) -> Image.Image:
    """Draw a window onto the content: rows are content rows, not screen rows."""
    if scroll is None:
        scroll = scroll_for(len(visible))
    img = BASE.copy()
    d = ImageDraw.Draw(img)
    window = [row for row in range(scroll, min(len(visible), scroll + VISIBLE))]
    tinted = signal_blocks(visible)

    for row in window:
        if row in tinted:
            y = px(TEXT_TOP + (row - scroll) * LINE_H)
            d.rectangle([px(INSET + 5), y - px(3), px(W - INSET - 5), y + px(19)], fill=TINT)
    for run in runs(tinted):
        first, last = max(run[0], scroll), min(run[-1], scroll + VISIBLE - 1)
        if first > last:
            continue
        y0 = px(TEXT_TOP + (first - scroll) * LINE_H) - px(3)
        y1 = px(TEXT_TOP + (last - scroll) * LINE_H) + px(19)
        d.rectangle([px(INSET + 5), y0, px(INSET + 8), y1],
                    fill=FLASH if run[0] in flash else FLAG)

    for row in window:
        line, kind = visible[row]
        y = px(TEXT_TOP + (row - scroll) * LINE_H)
        text = line.lstrip()
        indent = (len(line) - len(text) + 1) * SIZE * 0.55

        if kind == "cmd":
            if line.startswith("$ "):
                d.text((px(TEXT_LEFT), y), "$", font=FONT_BOLD, fill=PROMPT)
                x = TEXT_LEFT + d.textlength("$ ", font=FONT_BOLD) / S
                d.text((px(x), y), line[2:], font=FONT, fill=CMD)
            else:
                d.text((px(TEXT_LEFT + indent), y), text, font=FONT, fill=CMD)
        elif kind == "signal":
            end = line.index("]") + 1 if "]" in line else len(line)
            d.text((px(TEXT_LEFT), y), line[:end], font=FONT,
                   fill=FLASH if row in flash else FLAG)
            x = TEXT_LEFT + d.textlength(line[:end], font=FONT) / S
            d.text((px(x), y), line[end:], font=FONT, fill=CMD)
        elif kind == "fail":
            d.text((px(TEXT_LEFT), y), line, font=FONT, fill=ALERT)
        elif kind == "verdict":
            d.text((px(TEXT_LEFT), y), line, font=FONT_BOLD, fill=VERDICT_BAD)
        elif kind == "check":
            d.text((px(TEXT_LEFT + indent), y), text, font=FONT, fill=BODY)
        elif kind == "dim":
            d.text((px(TEXT_LEFT + indent), y), text, font=FONT, fill=DIM)
        else:
            d.text((px(TEXT_LEFT), y), line, font=FONT, fill=BODY)

    if cursor:
        row = len(visible) - 1
        if scroll <= row < scroll + VISIBLE:
            width = d.textlength(visible[row][0], font=FONT) / S
            y = px(TEXT_TOP + (row - scroll) * LINE_H)
            x = TEXT_LEFT + (width if not visible[row][0].startswith("$ ") else width)
            d.rectangle([px(x + 1), y - px(1), px(x + 9), y + px(17)], fill=CMD)
    return img


def story_frames() -> list:
    content = [(line, classify(line)) for line in demo_lines()]
    commands = [i for i, (line, kind) in enumerate(content)
                if kind == "cmd" and line.startswith("$ ")]
    frames: list = []
    shown: list = []

    def add(ms, flash=(), cursor=False):
        frames.append((render(shown, flash=flash, cursor=cursor), ms))

    def typed(prefix):
        frames.append((render(shown + [(prefix, "cmd")],
                              scroll_for(len(shown) + 1), cursor=True), 55))

    add(240)

    for position, start in enumerate(commands):
        end = commands[position + 1] if position + 1 < len(commands) else len(content)
        text = content[start][0]
        step = 4 if len(text) > 30 else 2
        for cut in range(step, len(text), step):
            typed(text[:cut])
        shown.append(content[start])
        add(100)

        pending: list = []

        def flush(ms_per_line: int = 85):
            """Output arrives in small batches: a frame costs ~25kB in the GIF."""
            if not pending:
                return
            shown.extend(pending)
            pending.clear()
            add(max(90, ms_per_line * 3))

        for index in range(start + 1, end):
            line, kind = content[index]
            if kind == "cmd":                    # a wrapped `--flag` continuation
                flush(60)
                shown.append(content[index])
                add(180)
                continue
            if kind == "signal":                 # pulse, then settle on its own frame
                flush()
                shown.append(content[index])
                add(90, flash={len(shown) - 1})
                add(80, flash={len(shown) - 1})
                continue
            pending.append(content[index])
            if not line.strip() or len(pending) >= 3:
                flush(60 if not line.strip() else 85)
        flush()
        add(1300 if position == len(commands) - 1 else 550)
    return frames


def build() -> list:
    story = story_frames()
    poster = story[-1][0]
    opening = story[0][0]

    frames = [(poster, 700)]                          # poster frame = the verdict
    for mix in (0.5, 1.0):                            # dissolve into the story
        frames.append((Image.blend(poster, opening, mix), 60))
    frames.extend(story)
    return frames


ACCENTS = [BG, CARD, TINT, BORDER, DIVIDER, CMD, BODY, DIM, FLAG, PROMPT,
           ALERT, *DOTS]


def palette(frames) -> Image.Image:
    """Palette from the art's own colours, with the accents forced in.

    Adaptive quantisation quietly dropped the green `$`: it is a few dozen
    pixels against a frame of greys, so median cut never spends a slot on it.
    """
    counts: dict = {}
    step = max(1, len(frames) // 8)
    for img in frames[::step]:
        for count, colour in img.getcolors(1 << 22):
            counts[colour] = counts.get(colour, 0) + count

    colours = [c for c, _ in sorted(counts.items(), key=lambda kv: -kv[1])][:72]
    for accent in ACCENTS:
        if all(sum((a - b) ** 2 for a, b in zip(accent, c)) > 144 for c in colours):
            colours.append(accent)

    pal = Image.new("P", (1, 1))
    chunk = colours[:256]
    pal.putpalette([v for c in chunk for v in c] + [0] * (768 - 3 * len(chunk)))
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
    for index, img in enumerate(flats):
        if preview is not None and index % max(1, len(frames) // 12) == 0:
            img.save(preview / f"frame-{index:03d}.png")
        paletted.append(img.quantize(palette=pal, dither=Image.Dither.NONE))

    paletted[0].save(OUT, save_all=True, append_images=paletted[1:],
                     duration=[ms for _, ms in frames], loop=0, optimize=True,
                     disposal=2)
    print(f"wrote {OUT} -- {len(frames)} frames, {W}x{H}, "
          f"{OUT.stat().st_size / 1024:.0f} KB, "
          f"{sum(ms for _, ms in frames) / 1000:.1f}s loop, {VISIBLE} rows visible")


if __name__ == "__main__":
    main()
