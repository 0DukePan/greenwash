#!/usr/bin/env python3
"""Build `assets/social-preview.png` -- the 1280x640 card GitHub, HN, X and
Slack render when the repo link is pasted. The repo has no cover image
without it, so the link unfurls as a grey rectangle with the repo name.

The checkmark here is not logo.svg re-encoded -- a rasterizer would embed a
dependency for one draw. It is the same shape redrawn from the same
coordinates: the rounded two-stroke check, the wet drip, and the spray dots,
rotated -4 degrees about the artboard centre exactly as logo.svg's transform
does, and filled with the same three-stop gradient. If logo.svg ever changes
materially, this file should change with it.

Text is set in the same Consolas-first stack as the demo GIF so the README
loop and the link card read as one product.

Run:  python assets/make_social_preview.py
"""

from __future__ import annotations

import math
import pathlib

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "social-preview.png"

S = 3                      # supersampling factor
W, H = 1280, 640           # GitHub's social-preview aspect

# Palette shared with assets/make_demo_gif.py: same dark, same ink, same
# signal colours, so the card and the demo loop agree with each other.
BG = (9, 12, 17)
CMD = (230, 237, 243)
DIM = (139, 148, 158)
FLAG = (240, 136, 62)
PROMPT = (63, 185, 80)

# logo.svg's paint gradient (stops at 0, 0.5, 1 along its own axis).
GRAD = [(0.0, (74, 222, 128)), (0.5, (34, 197, 94)), (1.0, (21, 128, 61))]

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


def font(style: str, size: float):
    for directory in FONT_DIRS:
        for name in FONT_FILES[style]:
            path = directory / name
            if path.is_file():
                return ImageFont.truetype(str(path), int(size * S))
    return ImageFont.load_default()


def px(value: float) -> int:
    return int(round(value * S))


def rotate(point, cx, cy, degrees):
    """SVG's rotate() in its y-down coordinate system."""
    rad = math.radians(degrees)
    cos_a, sin_a = math.cos(rad), math.sin(rad)
    x, y = point[0] - cx, point[1] - cy
    return (cx + x * cos_a - y * sin_a, cy + x * sin_a + y * cos_a)


def logo_mask(size: int) -> Image.Image:
    """The logo as a single-channel mask, drawn at 4x and reduced.

    Coordinates are logo.svg's 96x96 artboard after its own transform:
    translate(0, -7) then rotate(-4, 48, 48) -- the same wet checkmark the
    README shows at 76px, here at badge size.
    """
    ss = 4
    board = size * ss
    mask = Image.new("L", (board, board), 0)
    d = ImageDraw.Draw(mask)
    k = board / 96.0  # artboard unit -> drawn pixel

    def t(point):
        x, y = rotate(point, 48, 48, -4)
        return (x * k, (y - 7) * k)

    def line(points, width):
        pts = [t(p) for p in points]
        d.line(pts, fill=255, width=int(width * k), joint="curve")
        # round caps: the stroke ends are the check's visible corners
        r = width * k / 2
        for p in (pts[0], pts[-1]):
            d.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], fill=255)

    def blob(cx, cy, r):
        x, y = t((cx, cy))
        rr = r * k
        d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=255)

    # The check: corner -> crook -> tip, with the short heel that logo.svg's
    # path closes around (22.69, 49.31) -> (17.31, 54.69).
    line([(20.0, 52.0), (34.6, 70.4), (78.0, 26.0)], 12.8)
    line([(19.2, 51.4), (34.4, 69.8)], 12.8)

    # The wet drip hanging off the crook, and the spray off the tip --
    # raw artboard coordinates; t() applies logo.svg's own transform.
    line([(36.8, 78.0), (36.8, 84.4)], 5.2)
    blob(36.8, 92.2, 2.3)
    blob(41.6, 94.8, 1.0)
    blob(84.2, 16.4, 1.5)
    blob(88.6, 13.2, 0.9)
    blob(92.0, 10.8, 0.6)

    return mask.resize((size, size), Image.LANCZOS)


def gradient_fill(size: int, mask: Image.Image) -> Image.Image:
    """Ramp over the mask's occupied rows, following the logo's stops."""
    img = Image.new("RGB", (size, size), (0, 0, 0))
    bbox = mask.getbbox() or (0, 0, size, size)
    top, bottom = bbox[1], max(bbox[1] + 1, bbox[3])
    pxmap = img.load()
    maskmap = mask.load()
    for y in range(size):
        t_value = min(1.0, max(0.0, (y - top) / (bottom - top)))
        for i in range(len(GRAD) - 1):
            t0, c0 = GRAD[i]
            t1, c1 = GRAD[i + 1]
            if t0 <= t_value <= t1:
                f = (t_value - t0) / (t1 - t0) if t1 > t0 else 0.0
                colour = tuple(int(c0[j] + (c1[j] - c0[j]) * f) for j in range(3))
                break
        for x in range(size):
            if maskmap[x, y]:
                pxmap[x, y] = colour
    return img


def main() -> None:
    img = Image.new("RGB", (W * S, H * S), BG)
    d = ImageDraw.Draw(img)

    # Soft glow behind the mark, so the card is not a flat void.
    glow = Image.new("L", (W * S, H * S), 0)
    ImageDraw.Draw(glow).ellipse(
        [px(40), px(120), px(560), px(560)], fill=46)
    img.paste((22, 90, 50), (0, 0), glow.filter(ImageFilter.GaussianBlur(px(70))))

    # The mark, its drop shadow, then the mark itself.
    logo_size = px(400)
    mask = logo_mask(logo_size)
    shadow = mask.filter(ImageFilter.GaussianBlur(px(5)))
    img.paste((2, 8, 4), (px(70), px(124)), shadow)
    img.paste(gradient_fill(logo_size, mask), (px(70), px(118)), mask)

    # Wordmark and the hook. Measured, not eyeballed: every block is laid out
    # from its own textlength so the right margin holds at any font fallback.
    x0 = 512
    word = font("bold", 88)
    hook = font("bold", 54)
    small = font("regular", 26)

    d.text((px(x0), px(112)), "greenwash", font=word, fill=CMD)

    headline = [("Did your agent fix it,", CMD), ("or fake it?", FLAG)]
    y = 262
    for text, colour in headline:
        d.text((px(x0), px(y)), text, font=hook, fill=colour)
        y += 74

    d.text((px(x0), px(446)), "A trust report on a coding agent's \"done\".",
           font=small, fill=DIM)
    d.text((px(x0), px(508)), "github.com/0DukePan/greenwash",
           font=small, fill=PROMPT)

    out = img.resize((W, H), Image.LANCZOS)
    out.save(OUT, optimize=True)
    print(f"wrote {OUT} -- {W}x{H}, {OUT.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
