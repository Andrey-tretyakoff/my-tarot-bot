import asyncio
import os
import logging
import random
import re
from datetime import datetime, timedelta, date, timezone
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from meditations import get_meditation_of_day

# 📦 Импорты из модулей
from db import (init_db, register_user, set_user_zodiac, get_user_zodiac, log_usage,
                get_all_users, get_stats, save_astro_profile, get_astro_profile,
                delete_astro_profile, update_user_streak, claim_bonus)
from tarot_db import get_card, get_random_card, format_daily_message, escape_html, TAROT_DB
from image_gen import get_tarot_media, generate_ai_url
from lunar import get_lunar_day
from astro import calculate_daily_forecast

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
DB_PATH = os.getenv("DB_PATH", "tarot_bot.db")
MSK = ZoneInfo("Europe/Moscow")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
bot = Bot(token=BOT_TOKEN, timeout=60) # ✅ Таймаут увеличен
dp = Dispatcher()

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
async def send_with_fallback(message, card_name: str, caption: str):
    original_url, source = await get_tarot_media(card_name)
    logging.info(f"📤 Пробую отправить [{source}]: {card_name}")

    try:
        await message.answer_photo(photo=original_url, caption=caption, parse_mode="HTML")
        logging.info("✅ Оригинал отправлен успешно")
        return
    except TelegramBadRequest as e:
        logging.warning(f"⚠️ Оригинал отклонён: {e}")

    logging.info("🔄 Генерирую AI-фоллбэк...")
    ai_url = generate_ai_url(card_name)
    try:
        await message.answer_photo(photo=ai_url, caption=caption, parse_mode="HTML")
        logging.info("✅ AI-картинка отправлена успешно")
    except TelegramBadRequest as e:
        logging.warning(f"⚠️ AI тоже отклонён: {e}")
        await message.answer(caption, parse_mode="HTML")
    except Exception as e:
        logging.error(f"❌ Ошибка отправки: {e}")
        await message.answer(caption, parse_mode="HTML")


async def _send_daily_report(message: types.Message, user_id: int, zodiac_filter: str | None = None):
    context = "zodiac" if zodiac_filter else "general"
    tarot_data = get_card(user_id=user_id, zodiac=zodiac_filter, context=context)
    card_text = format_daily_message(tarot_data, zodiac_label=zodiac_filter)

    if len(card_text) > 1024:
        card_text = card_text[:1000] + "\n\n<i>...обрезано из-за лимита</i>"

    await send_with_fallback(message, tarot_data["name"], card_text)
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
        "date": date.today().isoformat()
    }

    caption = (
        f"🎁 <b>БОНУС ЗА {streak} ДНЕЙ!</b> 🏆\n\n"
        f"🌟 <b>{escape_html(tarot_data['name'])}</b>\n"
        f"{'🔄' if tarot_data['position'] == 'перевернутая' else '✨'} Позиция: {escape_html(tarot_data['position'].capitalize())}\n\n"
        f"💫 <b>Особое послание:</b>\n{escape_html(tarot_data['meaning'])}\n\n"
        f"<i>🔥 Вы получили эксклюзивную карту! Серия обновится завтра.</i>"
    )

    await send_with_fallback(message, tarot_data["name"], caption)
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
async def cmd_zodiac(message: types.Message):
    await message.answer("♈️ Выберите ваш знак зодиака:", reply_markup=zodiac_kb)


@dp.message(F.text.in_(ZODIAC_MAP.keys()))
async def handle_zodiac_select(message: types.Message):
    zodiac_key = ZODIAC_MAP[message.text]
    await set_user_zodiac(DB_PATH, message.from_user.id, zodiac_key)
    await message.answer(f"✅ Знак <b>{escape_html(message.text)}</b> сохранен! 🪐", parse_mode="HTML",
                         reply_markup=ReplyKeyboardRemove())

    # 👇 ИСПРАВЛЕНИЕ: вызываем функцию динамического меню
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
async def handle_get_card_zodiac(message: types.Message):
    user_zodiac = await get_user_zodiac(DB_PATH, message.from_user.id)
    if not user_zodiac:
        return await message.answer("⚠️ Сначала выберите знак зодиака:", reply_markup=zodiac_kb)

    await message.answer(f"🔮 Карта для {user_zodiac.capitalize()}...")
    streak_info = await update_user_streak(DB_PATH, message.from_user.id)

    if streak_info.get('is_bonus_day') and not streak_info.get('bonus_claimed'):
        await _send_bonus_card(message, message.from_user.id, streak_info['streak'])
    else:
        await _send_daily_report(message, message.from_user.id, zodiac_filter=user_zodiac)

    await _show_streak_ui(message, streak_info)


@dp.message(F.text == "🌙 Лунные сутки")
async def handle_lunar_day(message: types.Message):
    from lunar import get_lunar_day, get_weekly_energy_forecast
    from chart_gen import get_chart_url
    import os

    await bot.send_chat_action(chat_id=message.chat.id, action="upload_photo")
    today = get_lunar_day()
    week = get_weekly_energy_forecast()
    chart_path = get_chart_url(week)

    if not chart_path or not os.path.exists(chart_path):
        return await message.answer("❌ Ошибка генерации графика.")

    magic_note = f"\n✨ СЕГОДНЯ ОСОБО ДЛЯ МАГИИ: {today['magic_type']}" if today['is_magic_day'] else ""
    caption = (
        f"🌙 Лунный день: {today['lunar_day']} | {today['phase']}\n"
        f"⚡ Энергия: {today['energy']}% | Рекомендовано: {today['energy_percentage']}%\n"
        f"💫 {today['description']}{magic_note}\n\n"
        f"⏳ Смена лунных суток: {today['next_transition']}"
    )

    try:
        await asyncio.sleep(0.5)  # Даем диску завершить запись
        photo_file = FSInputFile(chart_path)
        await message.answer_photo(photo=photo_file, caption=caption, timeout=30)
    except Exception as e:
        print(f"❌ Ошибка отправки лунных суток: {e}")
        await message.answer(caption)
    finally:
        if os.path.exists(chart_path):
            os.remove(chart_path)


@dp.message(F.text == "📊 Статистика (админ)")
async def cmd_stats_button(message: types.Message):
    # Двойная проверка: даже если кнопку кто-то "подделает" текстом
    if message.from_user.id != ADMIN_ID:
        return await message.answer("⛔ Эта функция доступна только администратору.")

    stats = await get_stats(DB_PATH)
    if not stats:
        return await message.answer("📊 Статистики пока нет")

    text = "📊 <b>Последние 50 действий (сначала старые ↓):</b>\n\n"
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
            reply_markup=kb
        )
    else:
        if not user_zodiac:
            return await message.answer("⚠️ Сначала выберите знак зодиака:", reply_markup=zodiac_kb)
        await message.answer("🔮 Персональный астропрогноз\n\nОтправьте дату рождения (ДД.ММ.ГГГГ):")
        await state.set_state(AstroStates.waiting_birth_date)

@dp.callback_query(F.data == "astro_calc")
async def handle_astro_calc(cb: types.CallbackQuery):
    await cb.answer()
    profile = await get_astro_profile(DB_PATH, cb.from_user.id)
    if not profile or not profile.get("birth_date"):
        return await cb.message.answer("⚠️ Данные не найдены.")
    await cb.message.answer("⏳ Рассчитываю...")
    forecast = calculate_daily_forecast(
        profile["birth_date"],
        profile.get("birth_time", "00:00"),
        "Москва", "Москва" # Дефолтные города
    )
    await cb.message.answer(forecast)

@dp.callback_query(F.data == "astro_reset")
async def handle_astro_reset(cb: types.CallbackQuery, state: FSMContext):
    await cb.answer()
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
        "updated_at": datetime.now().isoformat()
    }
    await save_astro_profile(DB_PATH, message.from_user.id, profile_data)
    await state.clear()

    await message.answer("✅ Данные сохранены! Генерирую прогноз...")
    forecast = calculate_daily_forecast(
        profile_data["birth_date"], profile_data["birth_time"],
        profile_data["birth_place"], profile_data["current_place"]
    )
    await message.answer(forecast)


@dp.message(Command("cancel"))
async def cmd_cancel(message: types.Message, state: FSMContext):
    await state.clear()
    # 👇 ИСПОЛЬЗУЕМ ДИНАМИЧЕСКУЮ КЛАВИАТУРУ
    await message.answer("❌ Отменено. Выберите действие:", reply_markup=get_main_kb(message.from_user.id))





# ================= РУНЫ НЕДЕЛИ =================
@dp.message(F.text == "ᚠ Руны недели")
async def handle_runes_week(message: types.Message, state: FSMContext):
    from db import get_user_zodiac, get_astro_profile
    user_zodiac = await get_user_zodiac(DB_PATH, message.from_user.id)
    if not user_zodiac:
        return await message.answer("⚠️ Для рунического расклада нужно сначала выбрать знак зодиака:", reply_markup=zodiac_kb)

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
            reply_markup=kb
        )
    else:
        await message.answer("📅 Руны требуют точности. Отправь дату рождения (ДД.ММ.ГГГГ):")
        await state.update_data(zodiac=user_zodiac)
        await state.set_state(RuneStates.waiting_birth_date)

@dp.callback_query(F.data == "runes_use_saved")
async def cb_runes_saved(cb: types.CallbackQuery, state: FSMContext):
    await cb.answer()
    profile = await get_astro_profile(DB_PATH, cb.from_user.id)
    zodiac = await get_user_zodiac(DB_PATH, cb.from_user.id)
    await _run_runes_magic(cb.message, zodiac, profile["birth_date"], "unknown")

@dp.callback_query(F.data == "runes_new_data")
async def cb_runes_new(cb: types.CallbackQuery, state: FSMContext):
    await cb.answer()
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
    from runes_logic import get_weekly_rune_spread, RUNES_DB
    from rune_drawer import generate_rune_bytes  # ✅ Исправленный импорт
    from aiogram.types import BufferedInputFile

    status_msg = await message.answer("ᚠ Генерирую расклад...")
    try:
        # Синхронные вызовы здесь безопасны: они занимают <50мс
        text, rune_names = get_weekly_rune_spread(zodiac, birth_date, gender)
        symbols = [next((r['sym'] for r in RUNES_DB if r['ru'] == name), "?") for name in rune_names]

        # Генерация в RAM (без диска и потоков)
        photo_bytes = generate_rune_bytes(symbols[0], symbols[1], symbols[2])

        await status_msg.delete()

        if photo_bytes:
            await message.answer_photo(
                photo=BufferedInputFile(photo_bytes, filename="runes.jpg"),
                caption=text,
                timeout=60
            )
        else:
            await message.answer(text)

        await log_usage(DB_PATH, message.from_user.id, "Руны недели", "runes_spread", zodiac)

    except Exception as e:
        print(f"❌ Ошибка рун: {e}")
        await status_msg.delete()
        await message.answer("⚠️ Ошибка при раскладе. Попробуйте позже.",
                             reply_markup=get_main_kb(message.from_user.id))


# Функция "Магии" и отправки (Пункты 5, 6, 7, 8)
async def _run_runes_magic(message, zodiac, birth_date, gender):
    from runes_logic import get_weekly_rune_spread, RUNES_DB
    from rune_drawer import generate_rune_bytes

    # 1. Анимация магии
    magic_msg = await message.answer("🔮 Вхожу в транс...")
    await asyncio.sleep(1.5)
    await magic_msg.edit_text("🌀 Соединяю потоки энергии...")
    await asyncio.sleep(1.5)
    await magic_msg.edit_text("✨ Руны пробуждаются...")

    # 2. Генерация текста
    try:
        text, rune_names = get_weekly_rune_spread(zodiac, birth_date, gender)
        symbols = [next((r['sym'] for r in RUNES_DB if r['ru'] == name), "?") for name in rune_names]

        # 3. Рисование картинки
        image_path = generate_rune_bytes(symbols[0], symbols[1], symbols[2])

        await magic_msg.delete()  # Удаляем сообщение "Руны пробуждаются"

        # 4. Отправка
        if image_path and os.path.exists(image_path):
            await message.answer_photo(photo=FSInputFile(image_path), caption=text, parse_mode="HTML")
            os.remove(image_path)
        else:
            await message.answer(text, parse_mode="HTML")

        await log_usage(DB_PATH, message.from_user.id, "Руны недели", "runes_spread", zodiac)
    except Exception as e:
        print(f"Ошибка рун: {e}")
        await message.answer("⚠️ Произошла ошибка при раскладе. Попробуй позже.",
                             reply_markup=get_main_kb(message.from_user.id))

# ================= РАССЫЛКИ =================
async def daily_broadcast():
    logging.info("🚀 Запуск рассылки 9:00 МСК...")
    users = await get_all_users(DB_PATH)
    sent = blocked = 0
    for uid in users:
        try:
            u_zodiac = await get_user_zodiac(DB_PATH, uid)
            tarot_data = get_card(user_id=uid, zodiac=u_zodiac, context="zodiac")
            card_text = format_daily_message(tarot_data, zodiac_label=u_zodiac)
            if len(card_text) > 1024:
                card_text = card_text[:1000] + "\n\n..."

            orig, _ = await get_tarot_media(tarot_data["name"])
            try:
                await bot.send_photo(uid, photo=orig, caption=card_text, parse_mode="HTML")
            except TelegramBadRequest:
                await bot.send_photo(uid, photo=generate_ai_url(tarot_data["name"]), caption=card_text,
                                     parse_mode="HTML")

            await log_usage(DB_PATH, uid, tarot_data["name"], "broadcast", u_zodiac)
            sent += 1
            await asyncio.sleep(0.05)
        except (TelegramBadRequest, TelegramForbiddenError):
            blocked += 1
        except Exception as e:
            logging.error(f"Ошибка рассылки {uid}: {e}")
    logging.info(f"✅ Рассылка завершена. ✅{sent} | ❌{blocked}")


async def lunar_day_notification():
    logging.info("🌙 Запуск рассылки о лунных сутках на завтра...")
    tomorrow = datetime.now() + timedelta(days=1)
    lunar = get_lunar_day(tomorrow)
    users = await get_all_users(DB_PATH)
    sent = blocked = 0

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
            await bot.send_message(uid, text, parse_mode="HTML")
            sent += 1
            await asyncio.sleep(0.05)
        except (TelegramBadRequest, TelegramForbiddenError):
            blocked += 1
        except Exception as e:
            logging.error(f"Ошибка отправки лунных суток {uid}: {e}")
    logging.info(f"✅ Рассылка лунных суток завершена. ✅{sent} | ❌{blocked}")


def setup_scheduler():
    scheduler = AsyncIOScheduler(timezone=MSK)
    scheduler.add_job(daily_broadcast, "cron", hour=9, minute=0)
    scheduler.add_job(lunar_day_notification, "cron", hour=20, minute=0)
    scheduler.start()
    logging.info("📅 Планировщик запущен (9:00 - карты, 20:00 - лунные сутки)")
    return scheduler


# ================= ЗАПУСК =================
async def main():
    await init_db(DB_PATH)
    scheduler = setup_scheduler()
    try:
        logging.info("🤖 Бот запущен. Ожидание сообщений...")
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        logging.info("👋 Бот остановлен пользователем (Ctrl+C)")
    finally:
        scheduler.shutdown()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🤖 Бот остановлен. До связи!")