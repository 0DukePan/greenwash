#!/usr/bin/env python3
"""Build the small, shareable Greenwash meme card.

Unlike ``demo.gif``, this is not a terminal replay. It is the one-panel version
of the product idea: an agent's green check is a claim, and the receipt is the
evidence. Keep it distinct from the demo so the demo can stay an exact capture
of the real command.

Run: python assets/make_receipt_meme.py
"""

from __future__ import annotations

import pathlib

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "receipt-not-vibes.gif"

S = 3
W, H = 840, 480
BG_TOP, BG_BOTTOM = (8, 13, 17), (5, 9, 12)
CARD, BORDER, DIVIDER = (18, 20, 17), (61, 57, 49), (48, 44, 37)
TEXT, MUTED = (238, 235, 225), (167, 159, 145)
GREEN, GREEN_DARK, RED, ORANGE = (71, 218, 130), (21, 100, 57), (255, 116, 104), (243, 151, 76)

FONT_DIRS = [
    pathlib.Path(r"C:\Windows\Fonts"),
    pathlib.Path("/usr/share/fonts/truetype/dejavu"),
    pathlib.Path("/usr/share/fonts/truetype/liberation"),
    pathlib.Path("/System/Library/Fonts"),
]
FONT_FILES = {
    "regular": ["consola.ttf", "CascadiaMono.ttf", "DejaVuSansMono.ttf", "Menlo.ttc"],
    "bold": ["consolab.ttf", "CascadiaMono-Bold.ttf", "DejaVuSansMono-Bold.ttf"],
}


def px(value: float) -> int:
    return int(round(value * S))


def font(weight: str, size: float):
    for directory in FONT_DIRS:
        for name in FONT_FILES[weight]:
            candidate = directory / name
            if candidate.is_file():
                return ImageFont.truetype(str(candidate), px(size))
    return ImageFont.load_default()


F10, F12, F15, F18, F23 = (font("bold", size) for size in (10, 12, 15, 18, 23))
R12, R15 = font("regular", 12), font("regular", 15)


def rounded(draw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle([px(value) for value in box], radius=px(radius), fill=fill,
                           outline=outline, width=px(width))


def canvas() -> Image.Image:
    image = Image.new("RGB", (px(W), px(H)), BG_TOP)
    draw = ImageDraw.Draw(image)
    for y in range(px(H)):
        fraction = y / max(1, px(H) - 1)
        colour = tuple(round(BG_TOP[i] * (1 - fraction) + BG_BOTTOM[i] * fraction)
                       for i in range(3))
        draw.line([(0, y), (px(W), y)], fill=colour)

    glow = Image.new("RGBA", image.size, (0, 0, 0, 0))
    halo = ImageDraw.Draw(glow)
    halo.ellipse([px(15), px(105), px(350), px(430)], fill=(45, 196, 104, 32))
    return Image.alpha_composite(image.convert("RGBA"), glow.filter(ImageFilter.GaussianBlur(px(55)))).convert("RGB")


def text(draw, position, value, face, colour):
    draw.text((px(position[0]), px(position[1])), value, font=face, fill=colour)


def checkmark(draw, x, y, colour=GREEN):
    """An original wet-check mascot: the product's icon, not a borrowed character."""
    draw.line([(px(x + 13), px(y + 57)), (px(x + 47), px(y + 91)), (px(x + 122), px(y + 16))],
              fill=GREEN_DARK, width=px(28), joint="curve")
    draw.line([(px(x + 13), px(y + 57)), (px(x + 47), px(y + 91)), (px(x + 122), px(y + 16))],
              fill=colour, width=px(20), joint="curve")
    draw.ellipse([px(x + 43), px(y + 105), px(x + 52), px(y + 114)], fill=colour)
    draw.ellipse([px(x + 59), px(y + 114), px(x + 64), px(y + 119)], fill=colour)


def receipt(draw, x, y, alert: bool):
    """A tiny, legible evidence receipt that lands over the overconfident check."""
    rounded(draw, [x, y, x + 145, y + 152], 9, (244, 239, 224), outline=(184, 174, 152))
    text(draw, (x + 15, y + 17), "RECEIPT", F10, (67, 62, 52))
    draw.line([px(x + 15), px(y + 39), px(x + 130), px(y + 39)], fill=(185, 176, 157), width=px(1))
    text(draw, (x + 15, y + 53), "visible   1 / 1", R12, (55, 82, 62))
    text(draw, (x + 15, y + 78), "held-out  0 / 1", R12, (143, 48, 42) if alert else (92, 87, 75))
    draw.line([px(x + 15), px(y + 104), px(x + 130), px(y + 104)], fill=(185, 176, 157), width=px(1))
    text(draw, (x + 15, y + 116), "NOT VERIFIED" if alert else "CHECKING...", F10,
         RED if alert else (92, 87, 75))


def frame(step: int) -> Image.Image:
    image = canvas()
    draw = ImageDraw.Draw(image)
    rounded(draw, [28, 64, W - 28, H - 36], 12, CARD, outline=BORDER)
    draw.line([px(29), px(101), px(W - 29), px(101)], fill=DIVIDER, width=px(1))
    for index, colour in enumerate(((255, 96, 86), (250, 190, 57), GREEN)):
        cx = 47 + index * 16
        draw.ellipse([px(cx - 4), px(82 - 4), px(cx + 4), px(82 + 4)], fill=colour)
    text(draw, (83, 75), "greenwash / receipt check", F12, TEXT)
    text(draw, (W - 209, 76), "LOCAL • NO MODEL", F10, MUTED)

    # Left: the pleasant but insufficient green check.
    checkmark(draw, 76, 162)
    text(draw, (64, 316), "tests pass", F15, GREEN)
    text(draw, (64, 341), "confidence: immaculate", R12, MUTED)
    if step < 3:
        rounded(draw, [64, 366, 164, 399], 8, (20, 68, 42), outline=(42, 126, 76))
        text(draw, (78, 375), "SHIP IT?", F12, GREEN)
    else:
        rounded(draw, [64, 366, 202, 399], 8, (70, 31, 29), outline=(132, 54, 48))
        text(draw, (78, 375), "...maybe not.", F12, RED)
    if step >= 2:
        receipt(draw, 173, 146, alert=step >= 3)

    # Right: a deliberately short exchange. It is a meme, not a promise.
    text(draw, (374, 147), "YOUR AGENT:", F10, ORANGE)
    text(draw, (374, 174), '"Done. Tests pass."', F23, TEXT)
    if step >= 1:
        text(draw, (374, 230), "GREENWASH:", F10, GREEN)
        text(draw, (374, 256), '"Love that for you."', F18, TEXT)
        text(draw, (374, 282), '"Now show me the receipt."', F15, TEXT)
    if step >= 3:
        rounded(draw, [374, 316, 725, 367], 8, (67, 31, 29), outline=(122, 55, 48))
        text(draw, (390, 330), "× HELD-OUT TEST FAILED", F15, RED)
        text(draw, (374, 391), "Passed the vibe check. Not the test.", F15, ORANGE)
    elif step >= 2:
        text(draw, (374, 344), "checking the test the agent did not edit...", R12, MUTED)
    else:
        text(draw, (374, 344), "one more question before you ship it.", R12, MUTED)
    return image.resize((W, H), Image.Resampling.LANCZOS)


def main() -> None:
    # A pause, a question, then the punchline; final frame doubles as poster.
    plan = [(0, 850), (1, 1250), (2, 950), (3, 2200)]
    frames = [frame(step) for step, _ in plan]
    frames[0].save(OUT, save_all=True, append_images=frames[1:],
                   duration=[duration for _, duration in plan], loop=0,
                   optimize=True, disposal=2)
    print(f"wrote {OUT} -- {len(frames)} frames, {W}x{H}, "
          f"{OUT.stat().st_size / 1024:.0f} KB, "
          f"{sum(duration for _, duration in plan) / 1000:.1f}s loop")


if __name__ == "__main__":
    main()
