# rune_drawer.py
import io
from PIL import Image, ImageDraw, ImageFont


def generate_rune_bytes(rune1: str, rune2: str, rune3: str) -> bytes:
    """Генерирует картинку рун прямо в памяти, без записи на диск"""
    bg_path = "runes_bg.jpg"

    with Image.open(bg_path).convert("RGBA") as img:
        draw = ImageDraw.Draw(img)
        w, h = img.size

        try:
            font_symbol = ImageFont.truetype("arial.ttf", 120)
            font_label = ImageFont.truetype("arial.ttf", 35)
        except Exception:
            font_symbol = ImageFont.load_default()
            font_label = font_symbol

        positions = [(w * 0.25, h * 0.52), (w * 0.50, h * 0.52), (w * 0.75, h * 0.52)]
        runes = [rune1, rune2, rune3]
        labels = ["1. СИТУАЦИЯ", "2. ДЕЙСТВИЕ", "3. ИТОГ"]

        for i, rune in enumerate(runes):
            x, y = positions[i]
            draw.text((x, y), rune, fill="#FFD700", font=font_symbol, anchor="mm")
            draw.text((x, y + 100), labels[i], fill="#E0E0E0", font=font_label, anchor="mm")

        # Конвертируем в байты в памяти
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="JPEG", quality=75, optimize=True)
        buf.seek(0)
        return buf.read()