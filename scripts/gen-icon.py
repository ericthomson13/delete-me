"""Generate the delete-me product icon as a 1024x1024 PNG.

Design rationale: ties the icon to the brand mark in the Tauri UI nav —
a single bold 'M' (standing in for 'me', the thing the app deletes) with
a diagonal strikethrough in the accent purple. Rounded-square background
in a near-white fill (light) — Tauri's icon CLI fans this out to all
required platform sizes/formats, and macOS / Windows shells handle their
own masking/framing on top.

Usage:
    uv run python scripts/gen-icon.py [output_path]

Default output: tauri-app/src-tauri/icons/source.png
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

CANVAS = 1024
BG_PADDING = 56  # space around the rounded-square panel
PANEL_RADIUS = 192

# Theme colors mirror tauri-app/ui/src/app.css. Light-mode palette: the icon
# itself doesn't dark-mode (OS handles that contextually), so we pick the
# higher-contrast face.
PANEL_FILL = (250, 250, 252, 255)  # near-white with a hint of cool
PANEL_BORDER = (208, 215, 222, 255)  # --border light
LETTER_FILL = (31, 35, 40, 255)  # --fg light
STRIKE_FILL = (124, 58, 237, 255)  # --accent (#7c3aed)

LETTER = "M"
LETTER_SIZE = 720  # tuned so the M nearly fills the panel
STRIKE_THICKNESS = 56
STRIKE_ROTATION_DEG = -7  # matches the .brand .erased ::after rotate(-3deg) feel, slightly stronger at icon scale


def _resolve_font() -> ImageFont.FreeTypeFont:
    """Pick a heavy sans-serif that's present on the build machine."""
    candidates = [
        ("/System/Library/Fonts/HelveticaNeue.ttc", 11),  # Bold face index on macOS
        ("/System/Library/Fonts/Helvetica.ttc", 1),
        ("/System/Library/Fonts/Avenir.ttc", 8),
        ("/Library/Fonts/Arial Unicode.ttf", 0),
    ]
    for path, index in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, LETTER_SIZE, index=index)
            except (OSError, IndexError):
                continue
    # Last resort — bitmap default (will look bad but won't crash)
    return ImageFont.load_default()


def render(out_path: Path) -> None:
    img = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Rounded-square background panel
    panel = [BG_PADDING, BG_PADDING, CANVAS - BG_PADDING, CANVAS - BG_PADDING]
    draw.rounded_rectangle(
        panel,
        radius=PANEL_RADIUS,
        fill=PANEL_FILL,
        outline=PANEL_BORDER,
        width=4,
    )

    # Center the M
    font = _resolve_font()
    bbox = draw.textbbox((0, 0), LETTER, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    text_x = (CANVAS - text_w) / 2 - bbox[0]
    # textbbox returns whitespace above the cap line; nudge up slightly so the
    # M visually centers in the panel rather than the bbox-centers.
    text_y = (CANVAS - text_h) / 2 - bbox[1] - 28
    draw.text((text_x, text_y), LETTER, font=font, fill=LETTER_FILL)

    # Diagonal strikethrough — drawn on its own RGBA layer so we can rotate it
    # cleanly and composite.
    strike = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    sd = ImageDraw.Draw(strike)
    strike_y = CANVAS // 2
    strike_pad = CANVAS // 6  # extends a bit past the letter on both sides
    sd.rounded_rectangle(
        [strike_pad, strike_y - STRIKE_THICKNESS // 2,
         CANVAS - strike_pad, strike_y + STRIKE_THICKNESS // 2],
        radius=STRIKE_THICKNESS // 2,
        fill=STRIKE_FILL,
    )
    strike = strike.rotate(STRIKE_ROTATION_DEG, resample=Image.BICUBIC)
    img = Image.alpha_composite(img, strike)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG")
    print(f"wrote {out_path} ({CANVAS}x{CANVAS} RGBA)")


def main(argv: list[str]) -> int:
    if len(argv) > 1:
        out = Path(argv[1])
    else:
        out = Path(__file__).resolve().parent.parent / "tauri-app" / "src-tauri" / "icons" / "source.png"
    render(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
