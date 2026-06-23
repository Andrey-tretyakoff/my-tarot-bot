"""Локальные изображения Таро и знаков зодиака (без обязательного интернета)."""

from __future__ import annotations

import asyncio
import logging

from asset_loader import read_tarot_bytes, read_zodiac_bytes

logger = logging.getLogger(__name__)


async def get_tarot_image_bytes(card_name: str) -> tuple[bytes | None, str]:
    data, source = await asyncio.to_thread(read_tarot_bytes, card_name)
    if data:
        return data, source
    logger.warning("Картинка не найдена: %s", card_name)
    return None, "none"


async def get_zodiac_image_bytes(zodiac_key: str) -> tuple[bytes | None, str]:
    data = await asyncio.to_thread(read_zodiac_bytes, zodiac_key)
    if data:
        return data, "local"
    return None, "none"
