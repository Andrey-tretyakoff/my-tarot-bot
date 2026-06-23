# rune_drawer.py
import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from paths import ASSETS_DIR, ensure_runtime_dirs

RUNES_BG = ASSETS_DIR / "runes_bg.jpg"

_FONT_CANDIDATES = (
    ASSETS_DIR / "DejaVuSans.ttf",
    Path("C:/Windows/Fonts/arial.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
)


def _load_fonts() -> tuple[ImageFont.FreeTypeFont | ImageFont.ImageFont, ImageFont.FreeTypeFont | ImageFont.ImageFont]:
    for path in _FONT_CANDIDATES:
        if not path.exists():
            continue
        try:
            return (
                ImageFont.truetype(str(path), 120),
                ImageFont.truetype(str(path), 35),
            )
        except OSError:
            continue
    default = ImageFont.load_default()
    return default, default


def _default_background() -> Image.Image:
    img = Image.new("RGBA", (800, 600), (18, 22, 38, 255))
    draw = ImageDraw.Draw(img)
    for y in range(600):
        shade = int(18 + (y / 600) * 30)
        draw.line([(0, y), (800, y)], fill=(shade, shade + 8, shade + 24, 255))
    return img


def _open_background() -> Image.Image:
    ensure_runtime_dirs()
    if RUNES_BG.exists():
        return Image.open(RUNES_BG).convert("RGBA")
    return _default_background()


def generate_rune_bytes(rune1: str, rune2: str, rune3: str) -> bytes:
    """Генерирует картинку рун в памяти (фон из assets/ или программный fallback)."""
    with _open_background() as img:
        draw = ImageDraw.Draw(img)
        w, h = img.size
        font_symbol, font_label = _load_fonts()

        positions = [(w * 0.25, h * 0.52), (w * 0.50, h * 0.52), (w * 0.75, h * 0.52)]
        runes = [rune1, rune2, rune3]
        labels = ["1. СИТУАЦИЯ", "2. ДЕЙСТВИЕ", "3. ИТОГ"]

        for i, rune in enumerate(runes):
            x, y = positions[i]
            draw.text((x, y), rune, fill="#FFD700", font=font_symbol, anchor="mm")
            draw.text((x, y + 100), labels[i], fill="#E0E0E0", font=font_label, anchor="mm")

        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="JPEG", quality=75, optimize=True)
        buf.seek(0)
        return buf.read()
