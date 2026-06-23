"""Опциональная догрузка карт Таро с Wikimedia (выключена на Render по умолчанию)."""

from __future__ import annotations

import json
import logging
import os
import ssl
import time
import urllib.parse
import urllib.request
from pathlib import Path

from local_assets import read_local_tarot_bytes, read_local_zodiac_bytes
from network import get_proxy_url, ssl_verify_enabled
from paths import TAROT_DIR, ensure_runtime_dirs, tarot_asset_path

logger = logging.getLogger(__name__)

USER_AGENT = "TarotDayBot/1.0 (Telegram bot; educational tarot project)"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
DOWNLOAD_DELAY_SEC = 1.5

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


def remote_download_enabled() -> bool:
    return os.getenv("ENABLE_REMOTE_ASSETS", "").lower() in ("1", "true", "yes")


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


def _wikimedia_api_url(filename: str) -> str | None:
    params = urllib.parse.urlencode({
        "action": "query",
        "format": "json",
        "prop": "imageinfo",
        "iiprop": "url",
        "titles": f"File:{filename}",
    })
    raw = _http_get(f"{COMMONS_API}?{params}", timeout=25)
    if not raw:
        return None
    try:
        payload = json.loads(raw.decode("utf-8"))
        pages = payload.get("query", {}).get("pages", {})
        for page in pages.values():
            info = (page.get("imageinfo") or [{}])[0]
            url = info.get("url")
            if url:
                return url
    except (json.JSONDecodeError, KeyError, IndexError):
        pass
    return None


def _download_tarot_file(wiki_file: str, dest: Path) -> bool:
    url = _wikimedia_api_url(wiki_file)
    if not url:
        return False
    data = _http_get(url)
    if not data:
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    logger.info("Скачано: %s → %s", wiki_file, dest.name)
    return True


def ensure_all_tarot_assets() -> tuple[int, int]:
    """Догрузка недостающих карт (только если ENABLE_REMOTE_ASSETS=true)."""
    ensure_runtime_dirs()
    total = len(TAROT_WIKI_FILES)
    local_ok = sum(1 for name in TAROT_WIKI_FILES if tarot_asset_path(name).is_file())

    if not remote_download_enabled():
        logger.info("Таро (локально): %s/%s, удалённая загрузка выключена", local_ok, total)
        return local_ok, total

    ok = local_ok
    for card_name, wiki_file in TAROT_WIKI_FILES.items():
        dest = tarot_asset_path(card_name)
        if dest.is_file() and dest.stat().st_size > 300:
            continue
        if _download_tarot_file(wiki_file, dest):
            ok += 1
        time.sleep(DOWNLOAD_DELAY_SEC)

    logger.info("Таро: %s/%s (локально + догрузка)", ok, total)
    return ok, total


def read_tarot_bytes(card_name: str) -> bytes | None:
    return read_local_tarot_bytes(card_name)


def read_zodiac_bytes(zodiac_key: str) -> bytes | None:
    return read_local_zodiac_bytes(zodiac_key)
