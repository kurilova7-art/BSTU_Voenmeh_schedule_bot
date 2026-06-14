import sqlite3
import asyncio
import aiosqlite
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

DB_PATH = "../timetable.db"


# --- Инициализация базы данных ---
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS lessons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_number TEXT,
                day_of_week TEXT,
                week_type TEXT,
                time_start TEXT,
                time_end TEXT,
                discipline TEXT,
                lecturer_name TEXT,
                classroom TEXT,
                updated_at TIMESTAMP
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        await db.commit()


# --- Работа с таблицей lessons ---
async def clear_lessons_table():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM lessons")
        await db.commit()


async def insert_lesson(lesson_data: Dict[str, Any]):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO lessons (
                group_number, day_of_week, week_type, time_start, time_end,
                discipline, lecturer_name, classroom, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            lesson_data['group_number'],
            lesson_data['day_of_week'],
            lesson_data['week_type'],
            lesson_data['time_start'],
            lesson_data['time_end'],
            lesson_data['discipline'],
            lesson_data['lecturer_name'],
            lesson_data['classroom'],
            datetime.now()
        ))
        await db.commit()


async def insert_many_lessons(lessons_data: List[Dict]):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executemany('''
            INSERT INTO lessons (
                group_number, day_of_week, week_type, time_start, time_end,
                discipline, lecturer_name, classroom, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', [
            (
                l['group_number'], l['day_of_week'], l['week_type'],
                l['time_start'], l['time_end'], l['discipline'],
                l['lecturer_name'], l['classroom'], datetime.now()
            ) for l in lessons_data
        ])
        await db.commit()


# --- Метаданные ---
async def get_last_update_time() -> Optional[datetime]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM metadata WHERE key = 'last_update'") as cursor:
            row = await cursor.fetchone()
            if row:
                return datetime.fromisoformat(row[0])
    return None


async def set_last_update_time():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "REPLACE INTO metadata (key, value) VALUES (?, ?)",
            ('last_update', datetime.now().isoformat())
        )
        await db.commit()


# --- Поиск ---
async def search_lessons_by_group(group_number: str) -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM lessons WHERE group_number = ? ORDER BY day_of_week, time_start",
            (group_number,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def search_lessons_by_lecturer(lecturer_name: str) -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM lessons WHERE lecturer_name LIKE ? ORDER BY group_number, day_of_week, time_start",
            (f'%{lecturer_name}%',)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def search_lessons_by_classroom(classroom: str) -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM lessons WHERE classroom LIKE ? ORDER BY group_number, day_of_week, time_start",
            (f'%{classroom}%',)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def get_all_lecturers() -> List[str]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT DISTINCT lecturer_name FROM lessons WHERE lecturer_name != ''") as cursor:
            rows = await cursor.fetchall()
            lecturers = sorted(list(set([row[0].strip() for row in rows if row[0]])))
            return lecturers


async def get_groups_by_lecturer(lecturer_name: str) -> List[str]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT DISTINCT group_number FROM lessons WHERE lecturer_name LIKE ?", (f'%{lecturer_name}%',)) as cursor:
            rows = await cursor.fetchall()
            return sorted([row[0] for row in rows])


async def get_groups_by_classroom(classroom: str) -> List[str]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT DISTINCT group_number FROM lessons WHERE classroom LIKE ? AND classroom != ''", (f'%{classroom}%',)) as cursor:
            rows = await cursor.fetchall()
            return sorted([row[0] for row in rows])


# --- функции для календаря преподавателя и аудитории ---
async def search_lessons_by_lecturer_day_week(lecturer_name: str, day_of_week: str, week_type: str) -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM lessons WHERE lecturer_name LIKE ? AND day_of_week = ? AND week_type = ? ORDER BY time_start",
            (f'%{lecturer_name}%', day_of_week, week_type)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def search_lessons_by_classroom_day_week(classroom: str, day_of_week: str, week_type: str) -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM lessons WHERE classroom LIKE ? AND day_of_week = ? AND week_type = ? ORDER BY time_start",
            (f'%{classroom}%', day_of_week, week_type)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

