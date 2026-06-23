# astro.py - Продвинутый астропрогноз БЕЗ pyswisseph
# Использует: datetime, math, geopy (опционально)

import math
import random
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

MSK = ZoneInfo("Europe/Moscow")

# ================= КОНСТАНТЫ =================
ZODIAC_SIGNS = {
    "Овен": {"element": "Огонь", "quality": "Кардинальный", "ruler": "Марс",
             "traits": "инициатива, смелость, энергия", "lucky_day": "вторник", "lucky_color": "красный"},
    "Телец": {"element": "Земля", "quality": "Фиксированный", "ruler": "Венера",
              "traits": "стабильность, чувственность, практичность", "lucky_day": "пятница", "lucky_color": "зелёный"},
    "Близнецы": {"element": "Воздух", "quality": "Мутабельный", "ruler": "Меркурий",
                 "traits": "общение, интеллект, адаптивность", "lucky_day": "среда", "lucky_color": "жёлтый"},
    "Рак": {"element": "Вода", "quality": "Кардинальный", "ruler": "Луна",
            "traits": "интуиция, забота, эмоциональность", "lucky_day": "понедельник", "lucky_color": "белый"},
    "Лев": {"element": "Огонь", "quality": "Фиксированный", "ruler": "Солнце",
            "traits": "творчество, лидерство, щедрость", "lucky_day": "воскресенье", "lucky_color": "золотой"},
    "Дева": {"element": "Земля", "quality": "Мутабельный", "ruler": "Меркурий",
             "traits": "анализ, служение, точность", "lucky_day": "среда", "lucky_color": "синий"},
    "Весы": {"element": "Воздух", "quality": "Кардинальный", "ruler": "Венера",
             "traits": "гармония, дипломатия, красота", "lucky_day": "пятница", "lucky_color": "розовый"},
    "Скорпион": {"element": "Вода", "quality": "Фиксированный", "ruler": "Плутон",
                 "traits": "глубина, трансформация, страсть", "lucky_day": "вторник", "lucky_color": "бордовый"},
    "Стрелец": {"element": "Огонь", "quality": "Мутабельный", "ruler": "Юпитер",
                "traits": "оптимизм, философия, путешествия", "lucky_day": "четверг", "lucky_color": "фиолетовый"},
    "Козерог": {"element": "Земля", "quality": "Кардинальный", "ruler": "Сатурн",
                "traits": "дисциплина, амбиции, ответственность", "lucky_day": "суббота", "lucky_color": "чёрный"},
    "Водолей": {"element": "Воздух", "quality": "Фиксированный", "ruler": "Уран",
                "traits": "инновации, свобода, гуманизм", "lucky_day": "суббота", "lucky_color": "бирюзовый"},
    "Рыбы": {"element": "Вода", "quality": "Мутабельный", "ruler": "Нептун",
             "traits": "сострадание, воображение, духовность", "lucky_day": "четверг", "lucky_color": "морской"}
}

PLANET_DAYS = {
    "Солнце": "воскресенье", "Луна": "понедельник", "Марс": "вторник",
    "Меркурий": "среда", "Юпитер": "четверг", "Венера": "пятница", "Сатурн": "суббота"
}


# ================= ФУНКЦИИ РАСЧЁТА =================
def get_zodiac_sign(birth_date: str) -> str:
    """Определяет знак зодиака по дате рождения"""
    try:
        day, month, _ = map(int, birth_date.split('.'))
        signs = [
            ("Козерог", (1, 20), (2, 18)), ("Водолей", (1, 19), (2, 18)),
            ("Рыбы", (2, 19), (3, 20)), ("Овен", (3, 21), (4, 19)),
            ("Телец", (4, 20), (5, 20)), ("Близнецы", (5, 21), (6, 20)),
            ("Рак", (6, 21), (7, 22)), ("Лев", (7, 23), (8, 22)),
            ("Дева", (8, 23), (9, 22)), ("Весы", (9, 23), (10, 22)),
            ("Скорпион", (10, 23), (11, 21)), ("Стрелец", (11, 22), (12, 21)),
            ("Козерог", (12, 22), (1, 19))
        ]
        for sign, (start_m, start_d), (end_m, end_d) in signs:
            if (month == start_m and day >= start_d) or (month == end_m and day <= end_d):
                return sign
        return "Овен"
    except:
        return "Овен"


def calculate_moon_phase(date: datetime = None) -> dict:
    """Расчёт фазы Луны (упрощённый алгоритм)"""
    if date is None:
        date = datetime.now(MSK)
    elif date.tzinfo is None:
        date = date.replace(tzinfo=MSK)
    else:
        date = date.astimezone(MSK)

    known_new_moon = datetime(2024, 1, 11, 11, 57, tzinfo=MSK)
    lunar_cycle = 29.53058867
    days_since = (date - known_new_moon).total_seconds() / 86400
    moon_age = days_since % lunar_cycle
    phase = moon_age / lunar_cycle

    # Определение фазы
    if phase < 0.03 or phase > 0.97:
        name, emoji, energy = "Новолуние", "🌑", "закладка намерений"
    elif phase < 0.22:
        name, emoji, energy = "Растущая луна", "🌒", "набор сил, начало дел"
    elif phase < 0.28:
        name, emoji, energy = "Первая четверть", "🌓", "активные действия"
    elif phase < 0.47:
        name, emoji, energy = "Растущая луна", "🌔", "развитие проектов"
    elif phase < 0.53:
        name, emoji, energy = "Полнолуние", "🌕", "пик энергии, завершение"
    elif phase < 0.72:
        name, emoji, energy = "Убывающая луна", "🌖", "анализ, отпускание"
    elif phase < 0.78:
        name, emoji, energy = "Последняя четверть", "🌗", "избавление от лишнего"
    else:
        name, emoji, energy = "Убывающая луна", "🌘", "подготовка к новому"

    return {
        "phase": phase,
        "age": moon_age,
        "name": name,
        "emoji": emoji,
        "energy": energy,
        "illumination": int(phase * 100) if phase <= 0.5 else int((1 - phase) * 100)
    }


def get_planetary_hour(birth_time: str, date: datetime = None) -> str:
    """Определяет планетарный час (упрощённо)"""
    if date is None:
        date = datetime.now(MSK)

    try:
        hour = int(birth_time.split(':')[0]) if birth_time and ':' in birth_time else 12
    except:
        hour = 12

    planets = ["Сатурн", "Юпитер", "Марс", "Солнце", "Венера", "Меркурий", "Луна"]
    day_planet = planets[date.weekday() % 7]
    hour_planet = planets[(hour + planets.index(day_planet)) % 7]

    return hour_planet


def calculate_life_path_number(birth_date: str) -> int:
    """Расчёт числа жизненного пути (нумерология)"""
    try:
        numbers = [int(x) for x in birth_date if x.isdigit()]
        total = sum(numbers)
        while total > 9 and total not in [11, 22, 33]:
            total = sum(int(d) for d in str(total))
        return total
    except:
        return 1


# ================= ГЕНЕРАЦИЯ ПРОГНОЗА =================
def calculate_daily_forecast(birth_date: str, birth_time: str, birth_place: str, current_place: str) -> str:
    """Генерирует персонализированный прогноз с пояснениями"""

    # Базовые расчёты
    sign = get_zodiac_sign(birth_date)
    sign_data = ZODIAC_SIGNS[sign]
    moon = calculate_moon_phase()
    life_path = calculate_life_path_number(birth_date)
    today = datetime.now(MSK)
    today_str = today.strftime("%d.%m.%Y")
    weekday_num = today.weekday()  # 0=Пн, 6=Вс

    # 📚 Краткие значения чисел пути
    life_path_meanings = {
        1: "лидерство и новые начинания", 2: "партнёрство и интуиция",
        3: "творчество и самовыражение", 4: "стабильность и порядок",
        5: "свобода и перемены", 6: "забота и гармония",
        7: "анализ и духовность", 8: "успех и материальные цели",
        9: "сострадание и завершение"
    }

    # 🎨 Динамический цвет дня: (хеш даты + номер знака) % 7
    color_palette = ["золотой", "серебряный", "изумрудный", "лазурный", "рубиновый", "аметистовый", "янтарный"]
    date_hash = sum(ord(c) for c in today_str)
    sign_num = list(ZODIAC_SIGNS.keys()).index(sign)
    lucky_color = color_palette[(date_hash + sign_num) % len(color_palette)]

    # 🔮 Динамический талисман: знак + день недели + фаза Луны
    talismans = {
        "Овен": ["кристалл", "красная нить", "стальной амулет"],
        "Телец": ["зелёный камень", "монета", "растение"],
        "Близнецы": ["перо", "ключ", "зеркальце"],
        "Рак": ["жемчужина", "ракушка", "серебро"],
        "Лев": ["солнечный диск", "львиный коготь", "янтарь"],
        "Дева": ["травяной сбор", "кристалл соли", "блокнот"],
        "Весы": ["подвеска-весы", "розовый кварц", "лента"],
        "Скорпион": ["чёрный обсидиан", "ключ", "перстень"],
        "Стрелец": ["бирюза", "стрела", "карта"],
        "Козерог": ["чёрный агат", "часы", "гора"],
        "Водолей": ["электронный брелок", "голубой камень", "звезда"],
        "Рыбы": ["морской камень", "рыбка", "фиолетовый кристалл"]
    }
    moon_phase_talisman = "лунный камень" if moon['name'] == "Полнолуние" else "кристалл"
    daily_talisman = random.choice(talismans[sign])
    if moon['phase'] > 0.7:  # Убывающая
        daily_talisman = f"{daily_talisman} для очищения"
    elif moon['phase'] < 0.3:  # Растущая
        daily_talisman = f"{daily_talisman} для привлечения"

    # ⏰ Персонализированное время по стихии
    element = sign_data["element"]
    time_advice = {
        "Огонь": "• 🌅 Утро: старт проектов и смелые решения\n• ☀️ День: активные встречи и переговоры\n• 🌆 Вечер: спорт и творчество",
        "Земля": "• 🌅 Утро: планирование и рутина\n• ☀️ День: работа с документами и финансами\n• 🌆 Вечер: уют и забота о доме",
        "Воздух": "• 🌅 Утро: общение и обучение\n• ☀️ День: переписка и короткие поездки\n• 🌆 Вечер: идеи и вдохновение",
        "Вода": "• 🌅 Утро: медитация и отдых\n• ☀️ День: интуитивные решения и помощь другим\n• 🌆 Вечер: творчество и близкие"
    }

    # 💫 Аспект дня: планета-управитель знака + день недели
    planet_day = ["Луна", "Марс", "Меркурий", "Юпитер", "Венера", "Сатурн", "Солнце"][weekday_num]
    aspect_text = f"Сегодня {planet_day} поддерживает ваш знак {sign}. {sign_data['ruler']} в гармонии с днём."

    # 📝 Формирование прогноза
    forecast = (
        f"🔮 <b>Астропрогноз на {today_str}</b>\n\n"
        f"♈️ <b>Ваш знак:</b> {sign} ({sign_data['element']}, {sign_data['quality']})\n"
        f"🔢 <b>Число пути {life_path}:</b> {life_path_meanings.get(life_path, 'уникальный путь')}\n"
        f"🌍 <b>Локация:</b> {current_place}\n\n"

        f"━━━━━━━━━━━━━━━━━━\n\n"

        f"🌙 <b>Луна:</b> {moon['emoji']} {moon['name']}\n"
        f"💫 <i>Энергия дня:</i> {moon['energy']}\n\n"

        f"━━━━━━━━━━━━━━━━━━\n\n"

        f"✨ <b>Характеристики дня:</b>\n"
        f"• Планета-управитель: {sign_data['ruler']}\n"
        f"• Сильные стороны: {sign_data['traits']}\n"
        f"• Удачный день недели: {sign_data['lucky_day']}\n"
        f"• Цвет-талисман знака: {sign_data['lucky_color']}\n\n"

        f"🎨 <b>Цвет дня для вас:</b> {lucky_color}\n"
        f"🔮 <b>Талисман дня:</b> {daily_talisman}\n\n"

        f"⚡ <b>Аспект дня:</b>\n{aspect_text}\n\n"

        f"⏰ <b>Благоприятное время:</b>\n{time_advice[element]}\n\n"

        f"💡 <b>Совет звёзд:</b>\n{get_daily_advice(sign, life_path, moon['name'])}"
    )

    # Дополнительные заметки
    time_hint = (birth_time or "").strip().lower()
    if time_hint in ["не знаю", "неизвестно", "", "00:00"]:
        forecast += "\n\n<i>🕰️ Для точного расчёта асцендента укажите время рождения.</i>"

    return forecast


def get_daily_advice(sign: str, life_path: int, moon_phase: str) -> str:
    """Генерирует персонализированный совет"""
    base_advice = {
        "Овен": "Действуйте решительно, но слушайте других.",
        "Телец": "Не торопитесь — стабильность сегодня важнее скорости.",
        "Близнецы": "Общайтесь, но проверяйте информацию перед передачей.",
        "Рак": "Доверяйте интуиции, но не уходите в эмоции.",
        "Лев": "Проявите себя, но оставьте место другим.",
        "Дева": "Анализируйте, но не зацикливайтесь на деталях.",
        "Весы": "Ищите компромисс, но не жертвуйте своими интересами.",
        "Скорпион": "Идите вглубь, но не теряйте связь с реальностью.",
        "Стрелец": "Мечтайте, но делайте шаг за шагом.",
        "Козерог": "Ставьте цели, но не забывайте отдыхать.",
        "Водолей": "Будьте оригинальны, но учитывайте чувства других.",
        "Рыбы": "Творите, но заземляйте идеи в реальность."
    }

    # Корректировка по числу пути
    if life_path in [1, 8]:
        modifier = " Фокус на целях и результате."
    elif life_path in [2, 6]:
        modifier = " Уделите внимание отношениям."
    elif life_path in [3, 5]:
        modifier = " Позвольте себе спонтанность."
    elif life_path in [4, 7]:
        modifier = " Системный подход принесёт плоды."
    else:
        modifier = " Доверяйте своему уникальному пути."

    # Корректировка по фазе Луны
    if moon_phase == "Полнолуние":
        modifier += " Избегайте резких решений вечером."
    elif moon_phase == "Новолуние":
        modifier += " Идеальное время для новых намерений."

    return base_advice[sign] + modifier


# ================= ДОПОЛНИТЕЛЬНЫЕ ФУНКЦИИ =================
def get_compatibility(user_sign: str, partner_sign: str) -> str:
    """Совместимость знаков (для будущего расширения)"""
    elements = {sign: data["element"] for sign, data in ZODIAC_SIGNS.items()}
    if elements[user_sign] == elements[partner_sign]:
        return "Отличная совместимость! Общие элементы усиливают понимание."
    elif (elements[user_sign] in ["Огонь", "Воздух"] and elements[partner_sign] in ["Огонь", "Воздух"]) or \
            (elements[user_sign] in ["Земля", "Вода"] and elements[partner_sign] in ["Земля", "Вода"]):
        return "Хорошая совместимость. Гармоничное сочетание энергий."
    else:
        return "Противоположности притягиваются. Нужен компромисс."