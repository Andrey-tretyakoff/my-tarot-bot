from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
ASSETS_DIR = PROJECT_ROOT / "assets"
TAROT_DIR = ASSETS_DIR / "tarot"
ZODIAC_DIR = ASSETS_DIR / "zodiac"
TEMP_DIR = PROJECT_ROOT / "tmp"


def ensure_runtime_dirs() -> None:
    ASSETS_DIR.mkdir(exist_ok=True)
    TAROT_DIR.mkdir(exist_ok=True)
    ZODIAC_DIR.mkdir(exist_ok=True)
    TEMP_DIR.mkdir(exist_ok=True)


def find_lunar_background() -> Path | None:
    for candidate in (ASSETS_DIR / "bg_lunar.png", PROJECT_ROOT / "bg_lunar.png"):
        if candidate.is_file():
            return candidate
    return None


def tarot_asset_path(card_name: str) -> Path:
    safe = card_name.replace(" ", "_").replace("/", "_")
    return TAROT_DIR / f"{safe}.jpg"


def zodiac_asset_path(zodiac_key: str) -> Path:
    return ZODIAC_DIR / f"{zodiac_key.lower()}.png"
