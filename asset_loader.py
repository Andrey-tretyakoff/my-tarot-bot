"""Загрузка изображений Таро и знаков зодиака с Wikimedia Commons."""

from __future__ import annotations

import json
import logging
import ssl
import urllib.parse
import urllib.request
from pathlib import Path

from network import get_proxy_url, ssl_verify_enabled
from paths import TAROT_DIR, ZODIAC_DIR, ensure_runtime_dirs, tarot_asset_path, zodiac_asset_path

logger = logging.getLogger(__name__)

USER_AGENT = "TarotDayBot/1.0 (Telegram bot; educational tarot project)"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"

# Карты RWS: русское имя → имя файла на Wikimedia Commons
TAROT_WIKI_FILES: dict[str, str] = {
    "Шут": "RWS_Tarot_00_Fool.jpg",
    "Маг": "RWS_Tarot_01_Magician.jpg",
    "Верховная Жрица": "RWS_Tarot_02_High_Priestess.jpg",
    "Императрица": "RWS_Tarot_03_Empress.jpg",
    "Император": "RWS_Tarot_04_Emperor.jpg",
    "Иерофант": "RWS_Tarot_05_Hierophant.jpg",
    "Влюблённые": "TheLovers.jpg",
    "Колесница": "RWS_Tarot_07_Chariot.jpg",
    "Сила": "RWS_Tarot_08_Strength.jpg",
    "Отшельник": "RWS_Tarot_09_Hermit.jpg",
    "Колесо Фортуны": "RWS_Tarot_10_Wheel_of_Fortune.jpg",
    "Справедливость": "RWS_Tarot_11_Justice.jpg",
    "Повешенный": "RWS_Tarot_12_Hanged_Man.jpg",
    "Смерть": "RWS_Tarot_13_Death.jpg",
    "Умеренность": "RWS_Tarot_14_Temperance.jpg",
    "Дьявол": "RWS_Tarot_15_Devil.jpg",
    "Башня": "RWS_Tarot_16_Tower.jpg",
    "Звезда": "RWS_Tarot_17_Star.jpg",
    "Луна": "RWS_Tarot_18_Moon.jpg",
    "Солнце": "RWS_Tarot_19_Sun.jpg",
    "Суд": "RWS_Tarot_20_Judgement.jpg",
    "Мир": "RWS_Tarot_21_World.jpg",
    "Туз Жезлы": "Wands01.jpg",
    "2 Жезлы": "Wands02.jpg",
    "3 Жезлы": "Wands03.jpg",
    "4 Жезлы": "Wands04.jpg",
    "5 Жезлы": "Wands05.jpg",
    "6 Жезлы": "Wands06.jpg",
    "7 Жезлы": "Wands07.jpg",
    "8 Жезлы": "Wands08.jpg",
    "9 Жезлы": "Wands09.jpg",
    "10 Жезлы": "Wands10.jpg",
    "Паж Жезлы": "WandsPage.jpg",
    "Рыцарь Жезлы": "WandsKnight.jpg",
    "Королева Жезлы": "WandsQueen.jpg",
    "Король Жезлы": "WandsKing.jpg",
    "Туз Кубки": "Cups01.jpg",
    "2 Кубки": "Cups02.jpg",
    "3 Кубки": "Cups03.jpg",
    "4 Кубки": "Cups04.jpg",
    "5 Кубки": "Cups05.jpg",
    "6 Кубки": "Cups06.jpg",
    "7 Кубки": "Cups07.jpg",
    "8 Кубки": "Cups08.jpg",
    "9 Кубки": "Cups09.jpg",
    "10 Кубки": "Cups10.jpg",
    "Паж Кубки": "CupsPage.jpg",
    "Рыцарь Кубки": "CupsKnight.jpg",
    "Королева Кубки": "CupsQueen.jpg",
    "Король Кубки": "CupsKing.jpg",
    "Туз Мечи": "Swords01.jpg",
    "2 Мечи": "Swords02.jpg",
    "3 Мечи": "Swords03.jpg",
    "4 Мечи": "Swords04.jpg",
    "5 Мечи": "Swords05.jpg",
    "6 Мечи": "Swords06.jpg",
    "7 Мечи": "Swords07.jpg",
    "8 Мечи": "Swords08.jpg",
    "9 Мечи": "Swords09.jpg",
    "10 Мечи": "Swords10.jpg",
    "Паж Мечи": "SwordsPage.jpg",
    "Рыцарь Мечи": "SwordsKnight.jpg",
    "Королева Мечи": "SwordsQueen.jpg",
    "Король Мечи": "SwordsKing.jpg",
    "Туз Пентакли": "Pents01.jpg",
    "2 Пентакли": "Pents02.jpg",
    "3 Пентакли": "Pents03.jpg",
    "4 Пентакли": "Pents04.jpg",
    "5 Пентакли": "Pents05.jpg",
    "6 Пентакли": "Pents06.jpg",
    "7 Пентакли": "Pents07.jpg",
    "8 Пентакли": "Pents08.jpg",
    "9 Пентакли": "Pents09.jpg",
    "10 Пентакли": "Pents10.jpg",
    "Паж Пентакли": "PentsPage.jpg",
    "Рыцарь Пентакли": "PentsKnight.jpg",
    "Королева Пентакли": "PentsQueen.jpg",
    "Король Пентакли": "PentsKing.jpg",
}

ZODIAC_WIKI_FILES: dict[str, str] = {
    "овен": "Aries.svg",
    "телец": "Taurus.svg",
    "близнецы": "Gemini.svg",
    "рак": "Cancer.svg",
    "лев": "Leo.svg",
    "дева": "Virgo.svg",
    "весы": "Libra.svg",
    "скорпион": "Scorpio.svg",
    "стрелец": "Sagittarius.svg",
    "козерог": "Capricorn.svg",
    "водолей": "Aquarius.svg",
    "рыбы": "Pisces.svg",
}


def _build_opener() -> urllib.request.OpenerDirector:
    proxy = get_proxy_url()
    handlers: list = []
    if proxy:
        handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    if not ssl_verify_enabled():
        handlers.append(urllib.request.HTTPSHandler(context=ssl._create_unverified_context()))
    return urllib.request.build_opener(*handlers) if handlers else urllib.request.build_opener()


def _http_get(url: str, timeout: int = 40) -> bytes | None:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with _build_opener().open(request, timeout=timeout) as response:
            data = response.read()
            if len(data) > 300:
                return data
    except Exception as exc:
        logger.warning("GET %s: %s", url[:100], exc)
    return None


def _wikimedia_api_url(filename: str, *, thumb_width: int | None = None) -> str | None:
    iiprop = "url"
    params: dict[str, str | int] = {
        "action": "query",
        "format": "json",
        "prop": "imageinfo",
        "iiprop": iiprop,
        "titles": f"File:{filename}",
    }
    if thumb_width:
        params["iiprop"] = "url|thumburl"
        params["iiurlwidth"] = thumb_width
    encoded = urllib.parse.urlencode(params)
    raw = _http_get(f"{COMMONS_API}?{encoded}", timeout=25)
    if not raw:
        return None
    try:
        payload = json.loads(raw.decode("utf-8"))
        pages = payload.get("query", {}).get("pages", {})
        for page in pages.values():
            info = (page.get("imageinfo") or [{}])[0]
            if thumb_width and info.get("thumburl"):
                return info["thumburl"]
            url = info.get("url")
            if url:
                return url
    except (json.JSONDecodeError, KeyError, IndexError):
        pass
    return None


def _wikimedia_thumb_png(filename: str, width: int = 256) -> str | None:
    """PNG-превью для SVG-файлов знаков зодиака."""
    if filename.lower().endswith(".svg"):
        return _wikimedia_api_url(filename, thumb_width=width)
    return _wikimedia_api_url(filename)


def download_url_to_file(url: str, dest: Path) -> bool:
    data = _http_get(url)
    if not data:
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return True


def download_wikimedia_file(filename: str, dest: Path, *, as_png: bool = False) -> bool:
    if dest.exists() and dest.stat().st_size > 300:
        return True

    url = _wikimedia_thumb_png(filename) if as_png or filename.lower().endswith(".svg") else None
    if not url:
        url = _wikimedia_api_url(filename)
    if not url:
        logger.warning("Не удалось получить URL для %s", filename)
        return False

    if download_url_to_file(url, dest):
        logger.info("Скачано: %s → %s", filename, dest.name)
        return True

    if not as_png and filename.lower().endswith(".svg"):
        thumb = _wikimedia_thumb_png(filename)
        if thumb and download_url_to_file(thumb, dest):
            return True

    logger.warning("Не удалось скачать %s", filename)
    return False


def ensure_tarot_card(card_name: str) -> Path | None:
    ensure_runtime_dirs()
    dest = tarot_asset_path(card_name)
    if dest.exists():
        return dest

    wiki_file = TAROT_WIKI_FILES.get(card_name)
    if not wiki_file:
        logger.warning("Нет источника Wikimedia для карты: %s", card_name)
        return None

    if download_wikimedia_file(wiki_file, dest):
        return dest
    return None


def ensure_zodiac_sign(zodiac_key: str) -> Path | None:
    ensure_runtime_dirs()
    key = zodiac_key.lower().strip()
    dest = zodiac_asset_path(key)
    if dest.exists():
        return dest

    wiki_file = ZODIAC_WIKI_FILES.get(key)
    if not wiki_file:
        return None

    if download_wikimedia_file(wiki_file, dest, as_png=True):
        return dest
    return None


def ensure_all_tarot_assets() -> tuple[int, int]:
    """Скачивает все карты колоды RWS. Возвращает (успех, всего)."""
    ensure_runtime_dirs()
    ok = 0
    total = len(TAROT_WIKI_FILES)
    for card_name in TAROT_WIKI_FILES:
        if ensure_tarot_card(card_name):
            ok += 1
    logger.info("Таро: загружено %s/%s", ok, total)
    return ok, total


def ensure_all_zodiac_assets() -> tuple[int, int]:
    ensure_runtime_dirs()
    ok = 0
    total = len(ZODIAC_WIKI_FILES)
    for key in ZODIAC_WIKI_FILES:
        if ensure_zodiac_sign(key):
            ok += 1
    logger.info("Зодиак: загружено %s/%s", ok, total)
    return ok, total


def read_tarot_bytes(card_name: str) -> bytes | None:
    path = ensure_tarot_card(card_name)
    return path.read_bytes() if path else None


def read_zodiac_bytes(zodiac_key: str) -> bytes | None:
    path = ensure_zodiac_sign(zodiac_key)
    return path.read_bytes() if path else None
