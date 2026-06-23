import asyncio
import os
import sys
import logging
import random
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile, BufferedInputFile
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramNetworkError
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from meditations import get_meditation_of_day

# 📦 Импорты из модулей
from db import (init_db, register_user, set_user_zodiac, get_user_zodiac, log_usage,
                get_all_users, get_stats, save_astro_profile, get_astro_profile,
                delete_astro_profile, update_user_streak, claim_bonus,
                was_broadcast_sent, mark_broadcast_sent)
from tarot_db import get_card, format_daily_message, escape_html, TAROT_DB
from image_gen import get_tarot_image_bytes, get_zodiac_image_bytes
from lunar import get_lunar_day
from astro import calculate_daily_forecast
from network import get_proxy_url, ssl_verify_enabled
from instance_lock import acquire_single_instance, release_single_instance

if sys.platform == "win32":
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

load_dotenv()


class BotAiohttpSession(AiohttpSession):
    """Сессия с опцией отключения проверки SSL (нужно для VPN вроде Happ с HTTPS-перехватом)."""

    def __init__(self, proxy=None, ssl_verify: bool = True, **kwargs):
        super().__init__(proxy=proxy, **kwargs)
        if not ssl_verify:
            self._connector_init["ssl"] = False


BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
DB_PATH = os.getenv("DB_PATH", "tarot_bot.db")
TELEGRAM_PROXY = get_proxy_url()
TELEGRAM_SSL_VERIFY = ssl_verify_enabled()
MSK = ZoneInfo("Europe/Moscow")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def _validate_config() -> None:
    if not BOT_TOKEN or not BOT_TOKEN.strip():
        raise SystemExit(
            "❌ BOT_TOKEN не задан.\n"
            "Создайте файл .env в папке проекта и добавьте:\n"
            "BOT_TOKEN=токен_от_BotFather"
        )


def create_bot() -> Bot:
    _validate_config()

    if TELEGRAM_PROXY and TELEGRAM_PROXY.startswith("socks"):
        try:
            import aiohttp_socks  # noqa: F401
        except ImportError as exc:
            raise SystemExit(
                "❌ Для SOCKS-прокси установите пакет:\n"
                "pip install aiohttp-socks"
            ) from exc

    session = BotAiohttpSession(
        proxy=TELEGRAM_PROXY,
        ssl_verify=TELEGRAM_SSL_VERIFY,
    ) if TELEGRAM_PROXY else BotAiohttpSession(ssl_verify=TELEGRAM_SSL_VERIFY)
    if TELEGRAM_PROXY:
        source = "TELEGRAM_PROXY" if os.getenv("TELEGRAM_PROXY") else "системный прокси Windows"
        ssl_note = "" if TELEGRAM_SSL_VERIFY else " (SSL verify off)"
        logger.info("🌐 Telegram API через %s: %s%s", source, TELEGRAM_PROXY, ssl_note)

    return Bot(token=BOT_TOKEN, session=session)


bot = create_bot()
dp = Dispatcher(storage=MemoryStorage())

# ================= ВАЛИДАТОРЫ =================
def validate_date_format(date_str: str) -> str | None:
    if not re.match(r"^\d{2}\.\d{2}\.\d{4}$", date_str):
        return None
    try:
        dt = datetime.strptime(date_str, "%d.%m.%Y")
        if 1900 <= dt.year <= 2030:
            return date_str
    except ValueError:
        pass
    return None

def validate_time_format(time_str: str) -> str | None:
    clean = time_str.strip().lower()
    if clean in ["не знаю", "нет", "00:00", ""]:
        return "00:00"
    if re.match(r"^\d{2}:\d{2}$", clean):
        try:
            h, m = map(int, clean.split(":"))
            if 0 <= h <= 23 and 0 <= m <= 59:
                return clean
        except ValueError:
            pass
    return None

# ================= FSM =================
class AstroStates(StatesGroup):
    waiting_birth_date = State()
    waiting_birth_time = State()

class RuneStates(StatesGroup):
    waiting_birth_date = State()
    waiting_gender = State()

class ZodiacStates(StatesGroup):
    waiting_sign = State()

# Ключи для продолжения сценария после выбора знака
AFTER_ZODIAC_ASTRO = "astro"
AFTER_ZODIAC_RUNES = "runes"
AFTER_ZODIAC_CARD = "card_zodiac"

# ================= КЛАВИАТУРЫ =================
ZODIAC_SIGNS = [
    ("♈️ Овен", "овен"), ("♉️ Телец", "телец"), ("♊️ Близнецы", "близнецы"),
    ("♋️ Рак", "рак"), ("♌️ Лев", "лев"), ("♍️ Дева", "дева"),
    ("♎️ Весы", "весы"), ("♏️ Скорпион", "скорпион"), ("♐️ Стрелец", "стрелец"),
    ("♑️ Козерог", "козерог"), ("♒️ Водолей", "водолей"), ("♓️ Рыбы", "рыбы")
]
ZODIAC_MAP = {name: key for name, key in ZODIAC_SIGNS}

zodiac_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text=name) for name, _ in row] for row in
              [ZODIAC_SIGNS[i:i + 3] for i in range(0, 12, 3)]],
    resize_keyboard=True,
    input_field_placeholder="Выберите ваш знак зодиака:"
)




# ================= ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =================
async def send_tarot_photo(target, tarot_data: dict, caption: str):
    """Отправляет фото карты. tarot_data — единый объект расклада (имя, позиция, толкование)."""
    card_name = tarot_data["name"]
    photo_bytes, source = await get_tarot_image_bytes(card_name)
    logger.info("📤 Карта [%s]: %s", source, card_name)

    if photo_bytes:
        photo = BufferedInputFile(photo_bytes, filename="tarot.jpg")
        try:
            if isinstance(target, int):
                await bot.send_photo(target, photo=photo, caption=caption, parse_mode="HTML")
            else:
                await target.answer_photo(photo=photo, caption=caption, parse_mode="HTML")
            return True
        except TelegramBadRequest as exc:
            logger.warning("⚠️ Telegram отклонил фото: %s", exc)

    if isinstance(target, int):
        await bot.send_message(target, caption, parse_mode="HTML")
    else:
        await target.answer(caption, parse_mode="HTML")
    return False


async def _prompt_zodiac_for(message: types.Message, state: FSMContext, action: str) -> None:
    await state.update_data(after_zodiac=action)
    await state.set_state(ZodiacStates.waiting_sign)
    await message.answer("⚠️ Сначала выберите знак зодиака:", reply_markup=zodiac_kb)


async def _continue_astro_flow(message: types.Message, state: FSMContext) -> None:
    await state.clear()
    profile = await get_astro_profile(DB_PATH, message.from_user.id)
    user_zodiac = await get_user_zodiac(DB_PATH, message.from_user.id)

    if profile and profile.get("birth_date"):
        zodiac_text = f"♈️ Знак: {user_zodiac.capitalize()}" if user_zodiac else "⚠️ Знак не выбран"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Рассчитать по текущим данным", callback_data="astro_calc")],
            [InlineKeyboardButton(text="🔄 Ввести заново", callback_data="astro_reset")]
        ])
        await message.answer(
            f"🔮 Персональный астропрогноз\n\n"
            f"Сохраненные данные:\n📅 Дата: {profile['birth_date']}\n{zodiac_text}\n\n"
            f"Что делаем?",
            reply_markup=kb,
        )
    else:
        await message.answer("🔮 Персональный астропрогноз\n\nОтправьте дату рождения (ДД.ММ.ГГГГ):")
        await state.set_state(AstroStates.waiting_birth_date)


async def _continue_runes_flow(message: types.Message, state: FSMContext) -> None:
    user_zodiac = await get_user_zodiac(DB_PATH, message.from_user.id)
    profile = await get_astro_profile(DB_PATH, message.from_user.id)
    birth_date = profile.get("birth_date") if profile else None

    if birth_date:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Использовать сохраненные", callback_data="runes_use_saved")],
            [InlineKeyboardButton(text="🔄 Ввести новую дату", callback_data="runes_new_data")]
        ])
        await message.answer(
            f"ᚠ Руны недели\n\n"
            f"Сохраненные данные:\n♈️ Знак: {user_zodiac.capitalize()}\n📅 Дата: {birth_date}\n\n"
            f"Использовать их для расклада?",
            reply_markup=kb,
        )
    else:
        await message.answer("📅 Руны требуют точности. Отправь дату рождения (ДД.ММ.ГГГГ):")
        await state.update_data(zodiac=user_zodiac)
        await state.set_state(RuneStates.waiting_birth_date)


async def _continue_zodiac_card_flow(message: types.Message) -> None:
    user_zodiac = await get_user_zodiac(DB_PATH, message.from_user.id)
    await message.answer(
        f"🔮 Карта для {user_zodiac.capitalize()}...",
        reply_markup=get_main_kb(message.from_user.id),
    )
    streak_info = await update_user_streak(DB_PATH, message.from_user.id)

    if streak_info.get('is_bonus_day') and not streak_info.get('bonus_claimed'):
        await _send_bonus_card(message, message.from_user.id, streak_info['streak'])
    else:
        await _send_daily_report(message, message.from_user.id, zodiac_filter=user_zodiac)

    await _show_streak_ui(message, streak_info)


async def send_tarot_report(target, tarot_data: dict, caption: str):
    """Текст и изображение из одного объекта tarot_data."""
    await send_tarot_photo(target, tarot_data, caption)


async def send_zodiac_photo(target, zodiac_key: str, caption: str = ""):
    """Отправляет символ знака зодиака (локальный файл)."""
    photo_bytes, source = await get_zodiac_image_bytes(zodiac_key)
    if not photo_bytes:
        if caption:
            if isinstance(target, int):
                await bot.send_message(target, caption, parse_mode="HTML")
            else:
                await target.answer(caption, parse_mode="HTML")
        return False
    photo = BufferedInputFile(photo_bytes, filename="zodiac.png")
    try:
        if isinstance(target, int):
            await bot.send_photo(target, photo=photo, caption=caption or None, parse_mode="HTML")
        else:
            await target.answer_photo(photo=photo, caption=caption or None, parse_mode="HTML")
        logger.info("📤 Знак [%s]: %s", source, zodiac_key)
        return True
    except TelegramBadRequest as exc:
        logger.warning("⚠️ Telegram отклонил фото знака: %s", exc)
        return False


async def _send_daily_report(message: types.Message, user_id: int, zodiac_filter: str | None = None):
    context = "zodiac" if zodiac_filter else "general"
    tarot_data = get_card(user_id=user_id, zodiac=zodiac_filter, context=context)
    card_text = format_daily_message(tarot_data, zodiac_label=zodiac_filter)

    if len(card_text) > 1024:
        card_text = card_text[:1000] + "\n\n<i>...обрезано из-за лимита</i>"

    if zodiac_filter:
        await send_zodiac_photo(
            message,
            zodiac_filter,
            caption=f"♈️ Ваш знак: <b>{escape_html(zodiac_filter.capitalize())}</b>",
        )

    await send_tarot_report(message, tarot_data, card_text)
    await log_usage(DB_PATH, user_id, tarot_data["name"], "manual", zodiac_filter)


async def _send_bonus_card(message: types.Message, user_id: int, streak: int):
    """Отправляет эксклюзивную бонусную карту"""
    bonus_pool = [c for c in TAROT_DB if c['name'] in
                  ['Шут', 'Маг', 'Верховная Жрица', 'Императрица', 'Император', 'Иерофант',
                   'Влюблённые', 'Колесница', 'Сила', 'Отшельник', 'Колесо Фортуны', 'Справедливость',
                   'Повешенный', 'Смерть', 'Умеренность', 'Дьявол', 'Башня', 'Звезда', 'Луна', 'Солнце', 'Суд', 'Мир',
                   'Туз Жезлы', 'Туз Кубки', 'Туз Мечи', 'Туз Пентакли']]

    card = random.choice(bonus_pool)
    is_reversed = random.random() < 0.15

    tarot_data = {
        "name": card["name"],
        "position": "перевернутая" if is_reversed else "прямая",
        "meaning": card["rev"] if is_reversed else card["up"],
        "astro": card["astro"],
        "date": datetime.now(MSK).date().isoformat()
    }

    caption = (
        f"🎁 <b>БОНУС ЗА {streak} ДНЕЙ!</b> 🏆\n\n"
        f"🌟 <b>{escape_html(tarot_data['name'])}</b>\n"
        f"{'🔄' if tarot_data['position'] == 'перевернутая' else '✨'} Позиция: {escape_html(tarot_data['position'].capitalize())}\n\n"
        f"💫 <b>Особое послание:</b>\n{escape_html(tarot_data['meaning'])}\n\n"
        f"<i>🔥 Вы получили эксклюзивную карту! Серия обновится завтра.</i>"
    )

    await send_tarot_report(message, tarot_data, caption)
    await claim_bonus(DB_PATH, user_id)
    await log_usage(DB_PATH, user_id, tarot_data["name"], "bonus_7day", None)


async def _show_streak_ui(message: types.Message, streak_info: dict):
    """Показывает прогресс-бар серии"""
    streak = streak_info['streak']
    filled = min(streak, 7)
    empty = 7 - filled
    bar = "🔥" * filled + "⚪" * empty

    if streak_info['is_bonus_day'] and not streak_info['bonus_claimed']:
        note = "\n\n🎁 <b>Бонус доступен!</b> Нажмите кнопку карты, чтобы получить награду."
    elif streak >= 7:
        note = "\n\n✨ Серия завершена! Завтра начнётся новый цикл."
    else:
        days_left = 7 - streak
        note = f"\n\n<i>До бонуса осталось: {days_left} дн.</i>"

    if streak >= 3:
        await message.answer(f"📊 <b>Ваша серия:</b> {bar} ({streak}/7){note}", parse_mode="HTML")


def get_main_kb(user_id: int) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text="🃏 Карта дня"), KeyboardButton(text="♈️ Карта по знаку зодиака")],
        [KeyboardButton(text="🌙 Лунные сутки"), KeyboardButton(text="🔮 Астропрогноз")],
        [KeyboardButton(text="ᚠ Руны недели"), KeyboardButton(text="🧘 Медитация дня")] # Изменены эмодзи
    ]
    if user_id == ADMIN_ID:
        rows.append([KeyboardButton(text="📊 Статистика (админ)")])

    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        input_field_placeholder="Выберите действие:"
    )

# ================= ХЕНДЛЕРЫ =================
@dp.message(F.text == "🧘 Медитация дня")
async def handle_meditation(message: types.Message):
    meditation = get_meditation_of_day()
    caption = f"🧘 <b>Медитация дня</b>\n🎯 {meditation['title']}\n\n{meditation['text']}"

    # Проверка на длину (лимит Telegram 4096 символов)
    if len(caption) > 4000:
        caption = caption[:4000] + "..."

    await message.answer(caption, parse_mode="HTML")
    await log_usage(DB_PATH, message.from_user.id, meditation['title'], "meditation", None)


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await register_user(DB_PATH, message.from_user.id, message.from_user.username, message.from_user.first_name)
    user_zodiac = await get_user_zodiac(DB_PATH, message.from_user.id)
    zodiac_note = f"\n\n✅ <i>Ваш знак:</i> <b>{escape_html(user_zodiac.capitalize())}</b>" if user_zodiac else "\n\n⚙️ <i>Нажмите /zodiac, чтобы выбрать знак.</i>"
    welcome = f"👋 Добро пожаловать в <b>«Карта Дня»</b>!\n\nКаждое утро в <code>9:00 МСК</code> я пришлю вам карту Таро.{zodiac_note}\n\n✨ Кнопки ниже доступны всегда!"

    # 👇 ИСПОЛЬЗУЕМ ДИНАМИЧЕСКУЮ КЛАВИАТУРУ
    await message.answer(welcome, reply_markup=get_main_kb(message.from_user.id), parse_mode="HTML")


@dp.message(Command("zodiac"))
async def cmd_zodiac(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("♈️ Выберите ваш знак зодиака:", reply_markup=zodiac_kb)


@dp.message(F.text.in_(ZODIAC_MAP.keys()))
async def handle_zodiac_select(message: types.Message, state: FSMContext):
    zodiac_key = ZODIAC_MAP[message.text]
    await set_user_zodiac(DB_PATH, message.from_user.id, zodiac_key)

    data = await state.get_data()
    after_action = data.get("after_zodiac")
    current_state = await state.get_state()

    if current_state == ZodiacStates.waiting_sign.state and after_action:
        caption = f"✅ Знак <b>{escape_html(message.text)}</b> сохранён!"
        await send_zodiac_photo(message, zodiac_key, caption=caption)
        await message.answer("Продолжаем...", reply_markup=get_main_kb(message.from_user.id))

        if after_action == AFTER_ZODIAC_ASTRO:
            await _continue_astro_flow(message, state)
        elif after_action == AFTER_ZODIAC_RUNES:
            await _continue_runes_flow(message, state)
        elif after_action == AFTER_ZODIAC_CARD:
            await _continue_zodiac_card_flow(message)
        return

    caption = f"✅ Знак <b>{escape_html(message.text)}</b> сохранён! 🪐"
    if not await send_zodiac_photo(message, zodiac_key, caption=caption):
        await message.answer(caption, parse_mode="HTML", reply_markup=ReplyKeyboardRemove())
    await state.clear()
    await message.answer("Выберите действие:", reply_markup=get_main_kb(message.from_user.id))


@dp.message(F.text == "🃏 Карта дня")
async def handle_get_card_random(message: types.Message):
    await message.answer("🎴 Перемешиваю колоду...")
    streak_info = await update_user_streak(DB_PATH, message.from_user.id)

    if streak_info.get('is_bonus_day') and not streak_info.get('bonus_claimed'):
        await _send_bonus_card(message, message.from_user.id, streak_info['streak'])
    else:
        await _send_daily_report(message, message.from_user.id, zodiac_filter=None)

    await _show_streak_ui(message, streak_info)


@dp.message(F.text == "♈️ Карта по знаку зодиака")
async def handle_get_card_zodiac(message: types.Message, state: FSMContext):
    user_zodiac = await get_user_zodiac(DB_PATH, message.from_user.id)
    if not user_zodiac:
        return await _prompt_zodiac_for(message, state, AFTER_ZODIAC_CARD)

    await _continue_zodiac_card_flow(message)


@dp.message(F.text == "🌙 Лунные сутки")
async def handle_lunar_day(message: types.Message):
    from lunar import get_lunar_day, get_weekly_energy_forecast
    from chart_gen import get_chart_url

    await bot.send_chat_action(chat_id=message.chat.id, action="upload_photo")
    today = get_lunar_day()
    week = get_weekly_energy_forecast()
    chart_path = await asyncio.to_thread(get_chart_url, week)

    magic_note = f"\n✨ СЕГОДНЯ ОСОБО ДЛЯ МАГИИ: {today['magic_type']}" if today['is_magic_day'] else ""
    caption = (
        f"🌙 Лунный день: {today['lunar_day']} | {today['phase']}\n"
        f"⚡ Энергия: {today['energy']}% | Рекомендовано: {today['energy_percentage']}%\n"
        f"💫 {today['description']}{magic_note}\n\n"
        f"⏳ Смена лунных суток: {today['next_transition']}"
    )

    if not chart_path or not os.path.exists(chart_path):
        return await message.answer(caption)

    try:
        await message.answer_photo(photo=FSInputFile(chart_path), caption=caption, timeout=30)
    except Exception as exc:
        logger.error("Ошибка отправки лунных суток: %s", exc)
        await message.answer(caption)
    finally:
        if chart_path and os.path.exists(chart_path):
            os.remove(chart_path)


@dp.message(F.text == "📊 Статистика (админ)")
async def cmd_stats_button(message: types.Message):
    # Двойная проверка: даже если кнопку кто-то "подделает" текстом
    if message.from_user.id != ADMIN_ID:
        return await message.answer("⛔ Эта функция доступна только администратору.")

    stats = await get_stats(DB_PATH)
    if not stats:
        return await message.answer("📊 Статистики пока нет")

    text = "📊 <b>Последние 50 действий (сначала новые ↓):</b>\n\n"
    for username, first_name, u_zodiac, card, usage_type, z_filter, dt_str in stats:
        name = escape_html(username or first_name or "Пользователь")
        dt = datetime.fromisoformat(dt_str).strftime("%d.%m %H:%M")

        if usage_type == "broadcast":
            action = "📡 Рассылка"
        elif usage_type == "bonus_7day":
            action = "🎁 Бонус"
        elif z_filter:
            action = f"♈️ {escape_html(z_filter.capitalize())}"
        else:
            action = "🎴 Карта дня"

        text += f"👤 {name} | 🃏 {escape_html(card)} | 📱 {action} | 🕒 {dt}\n"

    if len(text) > 4000:
        text = text[:4000] + "\n\n... (и другие)"
    await message.answer(text, parse_mode="HTML")


@dp.message(Command("streak"))
async def cmd_streak(message: types.Message):
    """Показывает текущий статус серии"""
    from db import get_user_streak
    info = await get_user_streak(DB_PATH, message.from_user.id)
    bar = "🔥" * min(info['streak'], 7) + "⚪" * (7 - min(info['streak'], 7))
    text = f"📊 <b>Ваша серия посещений:</b>\n{bar} ({info['streak']}/7)\n\n"
    if info['bonus_available']:
        text += "🎁 <b>Бонус доступен!</b>\nНажмите 🔮 Карта дня или ♈️ Карта по знаку, чтобы получить эксклюзивную карту."
    elif info['streak'] >= 7:
        text += "✨ Серия завершена! Завтра начнётся новый цикл."
    else:
        days_left = 7 - info['streak']
        text += f"💪 Продолжайте заходить ежедневно! Осталось дней: {days_left}"
    await message.answer(text, parse_mode="HTML")




# ================= АСТРОПРОГНОЗ =================

@dp.message(F.text == "🔮 Астропрогноз")
async def handle_astro_start(message: types.Message, state: FSMContext):
    await state.clear()
    user_zodiac = await get_user_zodiac(DB_PATH, message.from_user.id)
    if not user_zodiac:
        return await _prompt_zodiac_for(message, state, AFTER_ZODIAC_ASTRO)
    await _continue_astro_flow(message, state)

@dp.callback_query(F.data == "astro_calc")
async def handle_astro_calc(cb: types.CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.clear()
    profile = await get_astro_profile(DB_PATH, cb.from_user.id)
    if not profile or not profile.get("birth_date"):
        return await cb.message.answer("⚠️ Данные не найдены. Введите дату заново через «🔄 Ввести заново».")
    await cb.message.answer("⏳ Рассчитываю...")
    try:
        forecast = calculate_daily_forecast(
            profile["birth_date"],
            profile.get("birth_time") or "00:00",
            profile.get("birth_place") or "Москва",
            profile.get("current_place") or "Москва",
        )
        await cb.message.answer(forecast, parse_mode="HTML")
    except Exception as exc:
        logger.exception("Ошибка астропрогноза: %s", exc)
        await cb.message.answer("⚠️ Не удалось рассчитать прогноз. Попробуйте «🔄 Ввести заново».")

@dp.callback_query(F.data == "astro_reset")
async def handle_astro_reset(cb: types.CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.clear()
    await delete_astro_profile(DB_PATH, cb.from_user.id)
    await cb.message.answer("🔄 Данные сброшены. Введите дату рождения (ДД.ММ.ГГГГ):")
    await state.set_state(AstroStates.waiting_birth_date)

@dp.message(AstroStates.waiting_birth_date)
async def astro_birth_date(message: types.Message, state: FSMContext):
    valid = validate_date_format(message.text)
    if not valid:
        return await message.answer("⚠️ Неверный формат. Отправьте дату как ДД.ММ.ГГГГ (год 1900-2030):")
    await state.update_data(birth_date=valid)
    await message.answer("🕰️ Время рождения (ЧЧ:ММ или 'не знаю'):")
    await state.set_state(AstroStates.waiting_birth_time)

@dp.message(AstroStates.waiting_birth_time)
async def astro_birth_time(message: types.Message, state: FSMContext):
    valid_time = validate_time_format(message.text)
    if not valid_time:
        return await message.answer("⚠️ Неверный формат времени. Напишите ЧЧ:ММ или 'не знаю':")

    data = await state.get_data()
    profile_data = {
        "birth_date": data["birth_date"],
        "birth_time": valid_time,
        "birth_place": "Москва",
        "current_place": "Москва",
        "updated_at": datetime.now(MSK).isoformat()
    }
    await save_astro_profile(DB_PATH, message.from_user.id, profile_data)
    await state.clear()

    await message.answer("✅ Данные сохранены! Генерирую прогноз...")
    try:
        forecast = calculate_daily_forecast(
            profile_data["birth_date"], profile_data["birth_time"],
            profile_data["birth_place"], profile_data["current_place"]
        )
        await message.answer(forecast, parse_mode="HTML")
    except Exception as exc:
        logger.exception("Ошибка астропрогноза: %s", exc)
        await message.answer("⚠️ Не удалось рассчитать прогноз. Попробуйте снова через «🔮 Астропрогноз».")


@dp.message(Command("cancel"))
async def cmd_cancel(message: types.Message, state: FSMContext):
    await state.clear()
    # 👇 ИСПОЛЬЗУЕМ ДИНАМИЧЕСКУЮ КЛАВИАТУРУ
    await message.answer("❌ Отменено. Выберите действие:", reply_markup=get_main_kb(message.from_user.id))





# ================= РУНЫ НЕДЕЛИ =================
@dp.message(F.text == "ᚠ Руны недели")
async def handle_runes_week(message: types.Message, state: FSMContext):
    user_zodiac = await get_user_zodiac(DB_PATH, message.from_user.id)
    if not user_zodiac:
        return await _prompt_zodiac_for(message, state, AFTER_ZODIAC_RUNES)
    await _continue_runes_flow(message, state)

@dp.callback_query(F.data == "runes_use_saved")
async def cb_runes_saved(cb: types.CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.clear()
    profile = await get_astro_profile(DB_PATH, cb.from_user.id)
    zodiac = await get_user_zodiac(DB_PATH, cb.from_user.id)
    if not profile or not profile.get("birth_date"):
        return await cb.message.answer("⚠️ Дата рождения не найдена. Введите её заново.")
    await _run_runes_magic(cb.message, zodiac, profile["birth_date"], "unknown")

@dp.callback_query(F.data == "runes_new_data")
async def cb_runes_new(cb: types.CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.clear()
    await cb.message.answer("📅 Отправь новую дату рождения (ДД.ММ.ГГГГ):")
    zodiac = await get_user_zodiac(DB_PATH, cb.from_user.id)
    await state.update_data(zodiac=zodiac)
    await state.set_state(RuneStates.waiting_birth_date)

@dp.message(RuneStates.waiting_birth_date)
async def rune_birth_date_handler(message: types.Message, state: FSMContext):
    valid = validate_date_format(message.text)
    if not valid:
        return await message.answer("⚠️ Неверный формат. Отправьте дату как ДД.ММ.ГГГГ (год от 1900 до 2030):")
    await state.update_data(birth_date=valid)
    await message.answer("👤 Укажи пол (влияет на энергетику):", reply_markup=ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Мужчина")], [KeyboardButton(text="Женщина")]], resize_keyboard=True
    ))
    await state.set_state(RuneStates.waiting_gender)

@dp.message(RuneStates.waiting_gender)
async def rune_gender_handler(message: types.Message, state: FSMContext):
    data = await state.get_data()
    gender_map = {"мужчина": "male", "женщина": "female"}
    gender = gender_map.get(message.text.lower().strip(), "unknown")
    await state.clear()
    await message.answer("✨ Данные приняты!", reply_markup=get_main_kb(message.from_user.id))
    await _run_runes_magic(message, data["zodiac"], data["birth_date"], gender)


async def _run_runes_magic(message, zodiac, birth_date, gender):
    from runes_logic import get_weekly_rune_spread

    status_msg = await message.answer("ᚠ Составляю расклад...")
    try:
        text, _ = await asyncio.to_thread(get_weekly_rune_spread, zodiac, birth_date, gender)
        await status_msg.delete()
        await message.answer(text, parse_mode="HTML")
        await log_usage(DB_PATH, message.from_user.id, "Руны недели", "runes_spread", zodiac)
    except Exception as e:
        logger.exception("❌ Ошибка рун: %s", e)
        await status_msg.delete()
        await message.answer(
            "⚠️ Ошибка при раскладе. Попробуйте позже.",
            reply_markup=get_main_kb(message.from_user.id),
        )


# ================= РАССЫЛКИ =================
async def daily_broadcast():
    logger.info("🚀 Запуск рассылки 9:00 МСК...")
    today = datetime.now(MSK).date().isoformat()
    users = await get_all_users(DB_PATH)
    sent = blocked = skipped = 0
    for uid in users:
        try:
            if await was_broadcast_sent(DB_PATH, uid, "daily_card", today):
                skipped += 1
                continue

            u_zodiac = await get_user_zodiac(DB_PATH, uid)
            tarot_data = get_card(user_id=uid, zodiac=u_zodiac, context="zodiac")
            card_text = format_daily_message(tarot_data, zodiac_label=u_zodiac)
            if len(card_text) > 1024:
                card_text = card_text[:1000] + "\n\n..."

            await send_tarot_photo(uid, tarot_data, card_text)
            await mark_broadcast_sent(DB_PATH, uid, "daily_card", today)
            await log_usage(DB_PATH, uid, tarot_data["name"], "broadcast", u_zodiac)
            sent += 1
            await asyncio.sleep(0.05)
        except (TelegramBadRequest, TelegramForbiddenError):
            blocked += 1
        except Exception as e:
            logger.error("Ошибка рассылки %s: %s", uid, e)
    logger.info("✅ Рассылка завершена. ✅%s | ⏭️%s | ❌%s", sent, skipped, blocked)


async def lunar_day_notification():
    logger.info("🌙 Запуск рассылки о лунных сутках на завтра...")
    tomorrow = datetime.now(MSK) + timedelta(days=1)
    sent_date = tomorrow.date().isoformat()
    lunar = get_lunar_day(tomorrow)
    users = await get_all_users(DB_PATH)
    sent = blocked = skipped = 0

    text = (
        f"🌙 <b>Лунный день на завтра ({tomorrow.strftime('%d.%m.%Y')})</b>\n\n"
        f"🔢 <b>Лунный день:</b> {lunar['lunar_day']}\n"
        f"🌓 <b>Фаза:</b> {lunar['phase']}\n"
        f"⚡ <b>Энергия:</b> {lunar['energy']}%\n\n"
        f"💫 <b>Что ждёт:</b>\n{lunar['description']}\n\n"
        f"📊 <b>Рекомендуемая активность:</b> {lunar['energy_percentage']}%\n\n"
        f"{'🌟 Отличный день для практик!' if lunar['good_for_energy'] else '💤 День для отдыха и рутины'}\n\n"
        f"<i>Нажмите 🌙 Лунные сутки в меню для подробностей</i>"
    )

    for uid in users:
        try:
            if await was_broadcast_sent(DB_PATH, uid, "lunar_evening", sent_date):
                skipped += 1
                continue
            await bot.send_message(uid, text, parse_mode="HTML")
            await mark_broadcast_sent(DB_PATH, uid, "lunar_evening", sent_date)
            sent += 1
            await asyncio.sleep(0.05)
        except (TelegramBadRequest, TelegramForbiddenError):
            blocked += 1
        except Exception as e:
            logger.error("Ошибка отправки лунных суток %s: %s", uid, e)
    logger.info("✅ Рассылка лунных суток завершена. ✅%s | ⏭️%s | ❌%s", sent, skipped, blocked)


def setup_scheduler():
    scheduler = AsyncIOScheduler(timezone=MSK)
    scheduler.add_job(daily_broadcast, "cron", hour=9, minute=0)
    scheduler.add_job(lunar_day_notification, "cron", hour=20, minute=0)
    scheduler.start()
    logging.info("📅 Планировщик запущен (9:00 - карты, 20:00 - лунные сутки)")
    return scheduler


# ================= ЗАПУСК =================
WEBHOOK_PATH = "/webhook"
PORT = int(os.getenv("PORT", "8080"))
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL", "").strip()
IS_RENDER = bool(os.getenv("RENDER"))
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "").strip() or None

scheduler: AsyncIOScheduler | None = None


async def ensure_telegram_connection(retries: int = 3) -> bool:
    """Проверяет доступ к Telegram API до старта."""
    for attempt in range(1, retries + 1):
        try:
            me = await bot.get_me()
            logger.info("✅ Telegram: @%s (id=%s)", me.username, me.id)
            return True
        except TelegramNetworkError:
            logger.warning(
                "Попытка %s/%s: нет связи с api.telegram.org",
                attempt, retries,
            )
            if attempt >= retries:
                logger.error(
                    "Не удалось подключиться к Telegram API.\n"
                    "На Render прокси не нужен — уберите TELEGRAM_PROXY из переменных окружения.\n"
                    "Локально: VPN Happ + TELEGRAM_PROXY=http://127.0.0.1:10809"
                )
                return False
            await asyncio.sleep(5)
    return False


def _preload_assets_sync() -> None:
    from local_assets import ensure_bundled_assets
    from asset_loader import ensure_all_tarot_assets
    ensure_bundled_assets()
    ensure_all_tarot_assets()


async def _preload_assets_background() -> None:
    """Фоновая загрузка карт — не блокирует старт HTTP-сервера."""
    logger.info("📦 Фоновая загрузка ассетов Таро/zodiac...")
    try:
        await asyncio.to_thread(_preload_assets_sync)
        logger.info("📦 Фоновая загрузка ассетов завершена")
    except Exception as exc:
        logger.exception("Ошибка фоновой загрузки ассетов: %s", exc)


def _start_scheduler() -> AsyncIOScheduler:
    global scheduler
    scheduler = setup_scheduler()
    return scheduler


def _stop_scheduler() -> None:
    global scheduler
    if scheduler:
        scheduler.shutdown()
        scheduler = None


async def _shutdown_bot() -> None:
    _stop_scheduler()
    await bot.session.close()
    if not IS_RENDER:
        release_single_instance()


async def _on_webhook_startup(_app) -> None:
    if not await ensure_telegram_connection():
        raise RuntimeError("Telegram API недоступен")
    base_url = RENDER_EXTERNAL_URL.rstrip("/")
    webhook_url = f"{base_url}{WEBHOOK_PATH}"
    await bot.set_webhook(
        webhook_url,
        secret_token=WEBHOOK_SECRET,
        drop_pending_updates=True,
    )
    logger.info("🔗 Webhook установлен: %s", webhook_url)
    _start_scheduler()
    asyncio.create_task(_preload_assets_background())


async def _on_webhook_shutdown(_app) -> None:
    await bot.delete_webhook(drop_pending_updates=False)
    await _shutdown_bot()


async def _health_handler(_request):
    from aiohttp import web
    return web.Response(text="ok")


async def _run_webhook_server() -> int:
    from aiohttp import web
    from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

    app = web.Application()
    app.router.add_get("/", _health_handler)
    app.router.add_get("/health", _health_handler)

    webhook_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=WEBHOOK_SECRET,
    )
    webhook_handler.register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    app.on_startup.append(_on_webhook_startup)
    app.on_cleanup.append(_on_webhook_shutdown)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=PORT)
    await site.start()
    logger.info("🌐 HTTP-сервер слушает 0.0.0.0:%s (режим webhook)", PORT)

    stop_event = asyncio.Event()
    try:
        await stop_event.wait()
    except KeyboardInterrupt:
        logger.info("👋 Остановка сервера...")
    finally:
        await runner.cleanup()
    return 0


async def _run_polling() -> int:
    if not IS_RENDER:
        acquire_single_instance()
    try:
        if not await ensure_telegram_connection():
            return 1
        _start_scheduler()
        asyncio.create_task(_preload_assets_background())
        logger.info("🤖 Бот запущен в режиме polling (локальная разработка)...")
        await dp.start_polling(bot)
        return 0
    except KeyboardInterrupt:
        logger.info("👋 Бот остановлен пользователем (Ctrl+C)")
        return 0
    finally:
        await _shutdown_bot()


async def main() -> int:
    from paths import ensure_runtime_dirs

    ensure_runtime_dirs()
    await init_db(DB_PATH)

    if RENDER_EXTERNAL_URL:
        return await _run_webhook_server()
    return await _run_polling()


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except KeyboardInterrupt:
        print("\n🤖 Бот остановлен. До связи!")