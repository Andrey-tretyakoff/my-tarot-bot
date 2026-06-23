import aiosqlite
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

MSK = ZoneInfo("Europe/Moscow")


def _msk_today_iso() -> str:
    return datetime.now(MSK).date().isoformat()


def _msk_yesterday_iso() -> str:
    return (datetime.now(MSK).date() - timedelta(days=1)).isoformat()


async def init_db(db_path: str):
    async with aiosqlite.connect(db_path) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                zodiac TEXT,
                streak_count INTEGER DEFAULT 0,
                last_visit_date TEXT DEFAULT NULL,
                bonus_claimed INTEGER DEFAULT 0,
                registered_at TEXT DEFAULT CURRENT_TIMESTAMP,
                started_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        await db.execute('''
            CREATE TABLE IF NOT EXISTS usage_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                card_name TEXT,
                usage_type TEXT,
                zodiac_filter TEXT,
                used_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        await db.execute('''
            CREATE TABLE IF NOT EXISTS astro_profiles (
                user_id INTEGER PRIMARY KEY,
                birth_date TEXT,
                birth_time TEXT,
                birth_place TEXT,
                birth_lat REAL,
                birth_lon REAL,
                current_place TEXT,
                updated_at TEXT
            )
        ''')

        await db.execute('''
            CREATE TABLE IF NOT EXISTS broadcast_log (
                user_id INTEGER NOT NULL,
                broadcast_type TEXT NOT NULL,
                sent_date TEXT NOT NULL,
                sent_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, broadcast_type, sent_date)
            )
        ''')

        for migration in (
            "ALTER TABLE users ADD COLUMN streak_count INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN last_visit_date TEXT DEFAULT NULL",
            "ALTER TABLE users ADD COLUMN bonus_claimed INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN started_at TEXT DEFAULT CURRENT_TIMESTAMP",
        ):
            try:
                await db.execute(migration)
            except Exception:
                pass

        await db.execute("PRAGMA journal_mode=WAL")
        await db.commit()


async def was_broadcast_sent(db_path: str, user_id: int, broadcast_type: str, sent_date: str) -> bool:
    async with aiosqlite.connect(db_path) as db:
        async with db.execute(
            "SELECT 1 FROM broadcast_log WHERE user_id=? AND broadcast_type=? AND sent_date=?",
            (user_id, broadcast_type, sent_date),
        ) as cur:
            return await cur.fetchone() is not None


async def mark_broadcast_sent(db_path: str, user_id: int, broadcast_type: str, sent_date: str):
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "INSERT OR IGNORE INTO broadcast_log (user_id, broadcast_type, sent_date, sent_at) VALUES (?, ?, ?, ?)",
            (user_id, broadcast_type, sent_date, datetime.now(MSK).isoformat()),
        )
        await db.commit()

async def register_user(db_path: str, user_id: int, username: str | None, first_name: str):
    async with aiosqlite.connect(db_path) as db:
        # Вставляем только явные данные. started_at заполнится автоматически
        await db.execute('''
            INSERT OR IGNORE INTO users (user_id, username, first_name)
            VALUES (?, ?, ?)
        ''', (user_id, username, first_name))
        await db.commit()

async def set_user_zodiac(db_path: str, user_id: int, zodiac: str):
    key = (zodiac or "").lower().strip()
    if not key:
        return
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            '''
            INSERT INTO users (user_id, zodiac)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET zodiac = excluded.zodiac
            ''',
            (user_id, key),
        )
        await db.commit()

async def get_user_zodiac(db_path: str, user_id: int) -> str | None:
    async with aiosqlite.connect(db_path) as db:
        async with db.execute('SELECT zodiac FROM users WHERE user_id = ?', (user_id,)) as cur:
            row = await cur.fetchone()
            return row[0] if row else None

async def log_usage(db_path: str, user_id: int, card_name: str, usage_type: str, zodiac_filter: str | None = None):
    async with aiosqlite.connect(db_path) as db:
        await db.execute('''INSERT INTO usage_log
            (user_id, card_name, usage_type, zodiac_filter, used_at) VALUES (?, ?, ?, ?, ?)''',
            (user_id, card_name, usage_type, zodiac_filter, datetime.now(MSK).isoformat()))
        await db.commit()

async def get_all_users(db_path: str):
    async with aiosqlite.connect(db_path) as db:
        async with db.execute("SELECT user_id FROM users") as cur:
            return [row[0] for row in await cur.fetchall()]


async def get_stats(db_path: str):
    try:
        async with aiosqlite.connect(db_path) as db:
            # 1. Явное ожидание курсора (стабильнее для aiosqlite)
            cursor = await db.execute('''
                SELECT u.username, u.first_name, u.zodiac, l.card_name, l.usage_type, l.zodiac_filter, l.used_at
                FROM usage_log l
                LEFT JOIN users u ON l.user_id = u.user_id
                ORDER BY l.used_at DESC
                LIMIT 50
            ''')
            rows = await cursor.fetchall()
            return list(reversed(rows))
    except Exception as e:
        # 2. Выводим точную ошибку SQLite в консоль
        print(f"⚠️ Ошибка SQL в get_stats: {e}")

        # 3. Фоллбэк: если JOIN падает, возвращаем просто логи без имён
        # Это предотвратит краш бота, пока вы не обновите БД
        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute(
                'SELECT user_id, card_name, usage_type, zodiac_filter, used_at FROM usage_log ORDER BY used_at DESC LIMIT 50')
            rows = await cursor.fetchall()
            return [(None, None, None, *row[1:]) for row in reversed(rows)]

async def update_user_streak(db_path: str, user_id: int) -> dict:
    """Обновляет серию посещений. Возвращает статус для UI."""
    today = _msk_today_iso()
    yesterday = _msk_yesterday_iso()

    async with aiosqlite.connect(db_path) as db:
        async with db.execute('SELECT streak_count, last_visit_date, bonus_claimed FROM users WHERE user_id = ?', (user_id,)) as cur:
            row = await cur.fetchone()
            streak, last_date, claimed = (row[0], row[1], row[2]) if row else (0, None, 0)

        # Если уже заходил сегодня — ничего не меняем
        if last_date == today:
            return {'streak': streak, 'is_bonus_day': False, 'bonus_claimed': claimed == 1}

        # Логика серии
        new_streak = streak + 1 if last_date == yesterday else 1
        new_claimed = 0  # Сбрасываем флаг бонуса для нового цикла
        is_bonus = (new_streak == 7)

        await db.execute('UPDATE users SET streak_count=?, last_visit_date=?, bonus_claimed=? WHERE user_id=?',
                         (new_streak, today, new_claimed, user_id))
        await db.commit()
        return {'streak': new_streak, 'is_bonus_day': is_bonus, 'bonus_claimed': False}

async def claim_bonus(db_path: str, user_id: int):
    """Фиксирует получение бонуса (чтобы не выдать дважды)"""
    async with aiosqlite.connect(db_path) as db:
        await db.execute('UPDATE users SET bonus_claimed=1 WHERE user_id=?', (user_id,))
        await db.commit()

async def save_astro_profile(db_path: str, user_id: int, data: dict):
    async with aiosqlite.connect(db_path) as db:
        await db.execute('''INSERT OR REPLACE INTO astro_profiles 
            (user_id, birth_date, birth_time, birth_place, birth_lat, birth_lon, current_place, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            (user_id,
             data.get('birth_date'),
             data.get('birth_time'),
             data.get('birth_place'),
             data.get('birth_lat', 0.0),
             data.get('birth_lon', 0.0),
             data.get('current_place'),
             data.get('updated_at')))
        await db.commit()

async def get_astro_profile(db_path: str, user_id: int) -> dict | None:
    async with aiosqlite.connect(db_path) as db:
        async with db.execute('SELECT * FROM astro_profiles WHERE user_id = ?', (user_id,)) as cur:
            row = await cur.fetchone()
            if row:
                return dict(zip(['user_id','birth_date','birth_time','birth_place','birth_lat','birth_lon','current_place','updated_at'], row))
    return None

async def delete_astro_profile(db_path: str, user_id: int):
    """Удаляет сохранённый астропрофиль пользователя"""
    async with aiosqlite.connect(db_path) as db:
        await db.execute('DELETE FROM astro_profiles WHERE user_id = ?', (user_id,))
        await db.commit()


async def get_user_streak(db_path: str, user_id: int) -> dict:
    """Получает текущий статус серии пользователя для команды /streak"""
    async with aiosqlite.connect(db_path) as db:
        async with db.execute(
            'SELECT streak_count, last_visit_date, bonus_claimed FROM users WHERE user_id = ?',
            (user_id,)
        ) as cur:
            row = await cur.fetchone()
            if row:
                streak, last_visit, bonus_claimed = row
                return {
                    'streak': streak or 0,
                    'last_visit': last_visit,
                    'bonus_available': (streak or 0) >= 7 and bonus_claimed == 0,
                    'bonus_claimed': bonus_claimed == 1
                }
    return {'streak': 0, 'last_visit': None, 'bonus_available': False, 'bonus_claimed': False}