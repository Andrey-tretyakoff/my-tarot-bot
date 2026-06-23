from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

MSK = ZoneInfo("Europe/Moscow")


def get_lunar_day(date: datetime = None) -> dict:
    if date is None:
        date = datetime.now(MSK)
    elif date.tzinfo is None:
        date = date.replace(tzinfo=MSK)

    known_new_moon = datetime(2024, 1, 11, 11, 57, tzinfo=timezone.utc)
    lunar_month = 29.53058867

    known_new_moon_local = known_new_moon.astimezone(date.tzinfo)
    days_since = (date - known_new_moon_local).total_seconds() / 86400
    lunar_age = days_since % lunar_month

    lunar_day = int(lunar_age) + 1
    phase = lunar_age / lunar_month

    # 🔧 Исправленный расчет времени смены
    fraction_to_next = 1.0 - (lunar_age % 1.0)
    if fraction_to_next <= 0.0001: fraction_to_next = 1.0
    seconds_to_next = fraction_to_next * 86400

    next_transition = date + timedelta(seconds=seconds_to_next)
    next_transition_str = next_transition.strftime("%H:%M")

    # Энергия и прочее (без изменений)
    if phase < 0.5:
        energy = int(phase * 2 * 100)
    else:
        energy = int((1 - phase) * 2 * 100)

    magic_days_list = [1, 11, 12, 15, 18, 19, 21, 23, 26, 29]
    is_magic_day = lunar_day in magic_days_list
    magic_types = {1: "намерения", 11: "сила", 12: "любовь", 15: "исполнение", 18: "защита", 19: "очищение",
                   21: "единство", 23: "трансформация", 26: "радость", 29: "завершение"}
    magic_type = magic_types.get(lunar_day, "")

    good_for_energy = lunar_day in [1, 11, 15, 23]
    energy_percentage = energy if good_for_energy else int(energy * 0.7)

    descriptions = {
        1: "🌑 Новолуние. День закладки намерений.", 2: "Начало роста. Хорош для старта.", 3: "День активности.",
        4: "День борьбы.", 5: "День любви.", 6: "День здоровья.", 7: "День силы.", 8: "День очищения.",
        9: "День кармы.", 10: "День семьи.",
        11: "🌟 ДЕНЬ СИЛЫ!", 12: "День любви к себе.", 13: "День трансформации.", 14: "День перед полнолунием.",
        15: "🌕 ПОЛНОЛУНИЕ.", 16: "День анализа.", 17: "День сомнений.", 18: "День тайн.", 19: "День врагов.",
        20: "День лени.", 21: "День энергии.", 22: "День путешествий.", 23: "🌟 ДЕНЬ ТРАНСФОРМАЦИИ.",
        24: "День разрушения.", 25: "День зрения.", 26: "День радости.", 27: "День мудрости.", 28: "День милосердия.",
        29: "День завершения.", 30: "День тишины."
    }

    return {
        "lunar_day": lunar_day,
        "phase": "🌒 Растущая" if phase < 0.5 else "🌘 Убывающая",
        "energy": energy, "energy_percentage": energy_percentage,
        "description": descriptions.get(lunar_day, ""),
        "next_transition": next_transition_str,
        "is_magic_day": is_magic_day, "magic_type": magic_type
    }


def get_weekly_energy_forecast(start_date: datetime = None) -> list[dict]:
    if start_date is None:
        start_date = datetime.now(MSK)
    elif start_date.tzinfo is None:
        start_date = start_date.replace(tzinfo=MSK)
    return [
        {
            "date": (start_date + timedelta(days=i)).strftime("%d.%m"),
            "energy_percentage": get_lunar_day(start_date + timedelta(days=i))['energy_percentage']
        }
        for i in range(7)
    ]