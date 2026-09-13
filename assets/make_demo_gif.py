#!/usr/bin/env python3
"""Build `assets/demo.gif` -- the README's terminal demo as a looping GIF.

Frames are drawn at 2x and downsampled, so text and corners come out
antialiased. Needs Pillow, a monospace font (Consolas, Cascadia Mono, DejaVu
Sans Mono, ...) and `assets/logo-mark.png`, which is `assets/logo.svg`
rasterized with a transparent background.

Run:  python assets/make_demo_gif.py [--preview DIR]
"""

from __future__ import annotations

import pathlib
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "demo.gif"
MARK = HERE / "logo-mark.png"

S = 2                      # supersampling factor
W, H = 860, 540            # final canvas
WIN = (40, 40, 820, 500)   # terminal window, final units
TITLE_H = 46
LEFT = 76
TOP = 120
LINE_H = 32
FPS = 45                   # ms per typing frame

BG_TOP, BG_BOTTOM = (9, 12, 17), (16, 22, 30)
PANEL, BORDER, DIVIDER = (13, 17, 23), (33, 38, 45), (28, 33, 40)
DOTS = [(255, 95, 86), (255, 189, 46), (39, 201, 63)]
TEXT, MUTED = (230, 237, 243), (139, 148, 158)
GREEN, ORANGE, RED = (63, 185, 80), (240, 136, 62), (248, 81, 73)

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
    "italic": ["consolai.ttf", "CascadiaMono-Italic.ttf", "DejaVuSansMono-Oblique.ttf"],
}


def font(style: str, size: int):
    for directory in FONT_DIRS:
        for name in FONT_FILES[style]:
            path = directory / name
            if path.is_file():
                return ImageFont.truetype(str(path), size * S)
    return ImageFont.load_default()


F_REG = font("regular", 20)
F_SMALL = font("regular", 15)
F_ITALIC = font("italic", 19)
F_BOLD = font("bold", 20)
F_MARK = font("bold", 46)
F_TAG = font("regular", 17)


def px(v: float) -> int:
    return int(round(v * S))


def mix(a, b, t: float):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def gradient() -> Image.Image:
    top = Image.new("RGB", (W * S, H * S), BG_TOP)
    bottom = Image.new("RGB", (W * S, H * S), BG_BOTTOM)
    mask = Image.new("L", (1, H * S))
    for y in range(H * S):
        mask.putpixel((0, y), int(255 * y / (H * S - 1)))
    return Image.composite(bottom, top, mask.resize((W * S, H * S)))


def chrome() -> Image.Image:
    img = gradient()
    x0, y0, x1, y1 = (px(v) for v in WIN)

    shadow = Image.new("L", img.size, 0)
    ImageDraw.Draw(shadow).rounded_rectangle(
        [x0 + px(4), y0 + px(10), x1 + px(4), y1 + px(12)], radius=px(18), fill=120)
    img.paste(Image.new("RGB", img.size, (0, 0, 0)), (0, 0),
              shadow.filter(ImageFilter.GaussianBlur(px(9))))

    d = ImageDraw.Draw(img)
    d.rounded_rectangle([x0, y0, x1, y1], radius=px(16), fill=PANEL, outline=BORDER, width=px(1))
    d.line([x0 + px(1), y0 + px(TITLE_H), x1 - px(1), y0 + px(TITLE_H)], fill=DIVIDER, width=px(1))
    for i, color in enumerate(DOTS):
        cx, cy = px(70 + 26 * i), y0 + px(23)
        d.ellipse([cx - px(7), cy - px(7), cx + px(7), cy + px(7)], fill=color)
    d.text(((x0 + x1) / 2, y0 + px(23)), "greenwash — demo", font=F_SMALL, fill=MUTED, anchor="mm")
    return img


BASE = chrome()
AGENT = 'Agent: "Done! tests/test_calc.py passes now."'
CMD = "greenwash scan"
HEAD = [("greenwash:", GREEN), (" 1 flag(s) -- explain these before calling it done.", TEXT)]
FLAG = [("  [hardcoded-return]", ORANGE), (" src/calc.py", TEXT)]
DETAIL = [("      returns literal 5 (directly or via a local),", MUTED),
          ("      which a test asserts against", MUTED)]
CHIP = "stop blocked  ·  exit 2"


def draw_parts(d: ImageDraw.ImageDraw, y: float, parts, alpha: float = 1.0):
    x = LEFT
    for text, color in parts:
        d.text((px(x), px(y)), text, font=F_REG, fill=mix(PANEL, color, alpha))
        x += d.textlength(text, font=F_REG) / S


def frame(agent_alpha=0.0, typed=0, cursor=False, head_alpha=0.0, lines=0,
          chip_alpha=0.0, chip_rise=0.0) -> Image.Image:
    img = BASE.copy()
    d = ImageDraw.Draw(img)
    if agent_alpha:
        d.text((px(LEFT), px(TOP)), AGENT, font=F_ITALIC, fill=mix(PANEL, MUTED, agent_alpha))
    if typed:
        x = LEFT
        d.text((px(x), px(TOP + 2 * LINE_H)), "$", font=F_BOLD, fill=GREEN)
        x += d.textlength("$ ", font=F_BOLD) / S
        d.text((px(x), px(TOP + 2 * LINE_H)), CMD[:typed], font=F_REG, fill=TEXT)
        x += d.textlength(CMD[:typed], font=F_REG) / S
        if cursor:
            d.rectangle([px(x + 1), px(TOP + 2 * LINE_H - 1), px(x + 11), px(TOP + 2 * LINE_H + 21)],
                        fill=mix(PANEL, TEXT, 0.9))
    if head_alpha:
        draw_parts(d, TOP + 4 * LINE_H, HEAD, head_alpha)
    if lines >= 1:
        draw_parts(d, TOP + 6 * LINE_H, FLAG)
    if lines >= 2:
        draw_parts(d, TOP + 7 * LINE_H, DETAIL[:1])
    if lines >= 3:
        draw_parts(d, TOP + 8 * LINE_H, DETAIL[1:])
    if chip_alpha:
        y = TOP + 9.6 * LINE_H + chip_rise
        font_chip = F_BOLD
        tw = d.textlength(CHIP, font=font_chip)
        box = [px(LEFT), px(y), px(LEFT) + tw + px(28), px(y + 34)]
        d.rounded_rectangle(box, radius=px(17), fill=mix(PANEL, (45, 18, 20), chip_alpha),
                            outline=mix(PANEL, RED, chip_alpha), width=px(1))
        d.text((px(LEFT) + px(14), px(y + 7)), CHIP, font=font_chip, fill=mix(PANEL, RED, chip_alpha))
    return img


def end_card() -> Image.Image:
    img = gradient()
    mark = Image.open(MARK).convert("RGBA").resize((px(160), px(160)), Image.LANCZOS)
    img.paste(mark, (px(W / 2) - mark.width // 2, px(118)), mark)
    d = ImageDraw.Draw(img)
    d.text((px(W / 2), px(322)), "greenwash", font=F_MARK, fill=TEXT, anchor="mm")
    d.text((px(W / 2), px(372)), "Catches coding agents that fake a passing test suite.",
           font=F_TAG, fill=MUTED, anchor="mm")
    return img


def build():
    frames = []

    def add(img, ms):
        frames.append((img, ms))

    add(frame(cursor=True), 420)
    for t in (0.35, 0.7, 1.0):
        add(frame(agent_alpha=t), 80)
    add(frame(agent_alpha=1.0), 320)
    for i in range(1, len(CMD) + 1):
        add(frame(agent_alpha=1.0, typed=i, cursor=True), FPS)
    add(frame(agent_alpha=1.0, typed=len(CMD), cursor=True), 260)
    add(frame(agent_alpha=1.0, typed=len(CMD), cursor=True, head_alpha=0.5), 70)
    add(frame(agent_alpha=1.0, typed=len(CMD), head_alpha=1.0), 200)
    add(frame(agent_alpha=1.0, typed=len(CMD), head_alpha=1.0, lines=1), 170)
    add(frame(agent_alpha=1.0, typed=len(CMD), head_alpha=1.0, lines=2), 150)
    add(frame(agent_alpha=1.0, typed=len(CMD), head_alpha=1.0, lines=3), 160)
    for t, rise in ((0.4, 8.0), (0.75, 3.5), (1.0, 0.0)):
        add(frame(agent_alpha=1.0, typed=len(CMD), head_alpha=1.0, lines=3,
                  chip_alpha=t, chip_rise=rise), 60)
    add(frame(agent_alpha=1.0, typed=len(CMD), head_alpha=1.0, lines=3, chip_alpha=1.0), 1500)

    last = frames[-1][0]
    blank = frame()
    for t in (0.3, 0.6, 0.85, 1.0):
        add(Image.blend(last, blank, t), 70)

    card = end_card()
    for t in (0.18, 0.36, 0.55, 0.74, 0.88, 1.0):
        add(Image.blend(blank, card, t), 85)
    add(card, 2200)

    # dissolve back toward the opening frame so the loop reads as intentional
    for t in (0.3, 0.6, 0.9):
        add(Image.blend(card, frames[0][0], t), 90)
    return frames


def main() -> None:
    frames = build()
    preview = None
    if "--preview" in sys.argv:
        preview = pathlib.Path(sys.argv[sys.argv.index("--preview") + 1])
        preview.mkdir(parents=True, exist_ok=True)

    palette_frames = []
    for i, (img, _) in enumerate(frames):
        if preview is not None and i % max(1, len(frames) // 12) == 0:
            img.save(preview / f"frame-{i:03d}.png")
        palette_frames.append(img.convert("P", palette=Image.ADAPTIVE, colors=64))

    palette_frames[0].save(
        OUT, save_all=True, append_images=palette_frames[1:],
        duration=[ms for _, ms in frames], loop=0, optimize=True, disposal=2)

    size = OUT.stat().st_size / 1024
    print(f"wrote {OUT} -- {len(frames)} frames, {size:.0f} KB, "
          f"{sum(ms for _, ms in frames) / 1000:.1f}s loop")


if __name__ == "__main__":
    main()
