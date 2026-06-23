"""Локальные заглушки и генерация знаков зодиака без интернета."""

from __future__ import annotations

import io
import logging
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from paths import ASSETS_DIR, TAROT_DIR, ZODIAC_DIR, ensure_runtime_dirs, tarot_asset_path, zodiac_asset_path

logger = logging.getLogger(__name__)

PLACEHOLDER_TAROT = ASSETS_DIR / "placeholder_tarot.jpg"
PLACEHOLDER_ZODIAC = ASSETS_DIR / "placeholder_zodiac.png"

ZODIAC_LABELS: dict[str, tuple[str, str]] = {
    "овен": ("♈", "Овен"),
    "телец": ("♉", "Телец"),
    "близнецы": ("♊", "Близнецы"),
    "рак": ("♋", "Рак"),
    "лев": ("♌", "Лев"),
    "дева": ("♍", "Дева"),
    "весы": ("♎", "Весы"),
    "скорпион": ("♏", "Скорпион"),
    "стрелец": ("♐", "Стрелец"),
    "козерог": ("♑", "Козерог"),
    "водолей": ("♒", "Водолей"),
    "рыбы": ("♓", "Рыбы"),
}

BG_COLOR = (15, 32, 72)
GOLD = (255, 215, 0)
WHITE = (240, 240, 255)


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for name in ("segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _draw_zodiac_png(key: str, symbol: str, label: str) -> bytes:
    img = Image.new("RGBA", (256, 256), (*BG_COLOR, 255))
    draw = ImageDraw.Draw(img)
    symbol_font = _load_font(96)
    label_font = _load_font(28)
    sym_box = draw.textbbox((0, 0), symbol, font=symbol_font)
    sym_w = sym_box[2] - sym_box[0]
    sym_h = sym_box[3] - sym_box[1]
    draw.text(((256 - sym_w) / 2, 70 - sym_h / 2), symbol, fill=GOLD, font=symbol_font)
    lbl_box = draw.textbbox((0, 0), label, font=label_font)
    lbl_w = lbl_box[2] - lbl_box[0]
    draw.text(((256 - lbl_w) / 2, 190), label, fill=WHITE, font=label_font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _draw_tarot_placeholder(card_name: str | None = None) -> bytes:
    img = Image.new("RGB", (400, 700), (20, 12, 48))
    draw = ImageDraw.Draw(img)
    draw.rectangle([20, 20, 380, 680], outline=GOLD, width=4)
    title_font = _load_font(42)
    sub_font = _load_font(22)
    name_font = _load_font(18)
    draw.text((110, 280), "ТАРО", fill=GOLD, font=title_font)
    draw.text((70, 340), "Карта дня", fill=WHITE, font=sub_font)
    if card_name:
        label = card_name.replace(" ", "\n") if len(card_name) > 14 else card_name
        box = draw.textbbox((0, 0), label, font=name_font)
        tw = box[2] - box[0]
        draw.text(((400 - tw) / 2, 420), label, fill=GOLD, font=name_font, align="center")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def tarot_placeholder_bytes(card_name: str | None = None) -> bytes:
    """Нейтральная заглушка — никогда не копирует изображение другой карты."""
    return _draw_tarot_placeholder(card_name)


def ensure_placeholder_tarot() -> Path:
    ensure_runtime_dirs()
    # Старые заглушки могли быть скопированы из реальной карты (>100 KB)
    if PLACEHOLDER_TAROT.is_file() and PLACEHOLDER_TAROT.stat().st_size < 100_000:
        return PLACEHOLDER_TAROT
    PLACEHOLDER_TAROT.write_bytes(_draw_tarot_placeholder())
    logger.info("Нейтральная заглушка Таро создана")
    return PLACEHOLDER_TAROT


def ensure_local_zodiac(key: str) -> Path:
    ensure_runtime_dirs()
    path = zodiac_asset_path(key)
    if path.is_file() and path.stat().st_size > 200:
        return path
    symbol, label = ZODIAC_LABELS.get(key.lower(), ("★", key.capitalize()))
    path.write_bytes(_draw_zodiac_png(key, symbol, label))
    logger.info("Локальный знак зодиака: %s", path.name)
    return path


def ensure_all_zodiac_local() -> tuple[int, int]:
    ensure_runtime_dirs()
    ok = 0
    for key in ZODIAC_LABELS:
        if ensure_local_zodiac(key):
            ok += 1
    logger.info("Зодиак (локально): %s/%s", ok, len(ZODIAC_LABELS))
    return ok, len(ZODIAC_LABELS)


def ensure_bundled_assets() -> None:
    ensure_placeholder_tarot()
    ensure_all_zodiac_local()


def read_local_tarot_bytes(card_name: str) -> tuple[bytes | None, str]:
    """Возвращает (bytes, source): local | placeholder."""
    path = tarot_asset_path(card_name)
    if path.is_file() and path.stat().st_size > 300:
        return path.read_bytes(), "local"
    return tarot_placeholder_bytes(card_name), "placeholder"


def read_local_zodiac_bytes(zodiac_key: str) -> bytes | None:
    try:
        return ensure_local_zodiac(zodiac_key.lower().strip()).read_bytes()
    except OSError as exc:
        logger.warning("Не удалось прочитать знак %s: %s", zodiac_key, exc)
        if PLACEHOLDER_ZODIAC.is_file():
            return PLACEHOLDER_ZODIAC.read_bytes()
        return _draw_zodiac_png("default", "★", "Знак")
