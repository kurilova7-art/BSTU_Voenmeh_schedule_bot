import asyncio
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Dict, List
from datetime import datetime, date
from utils import database as db
import aiohttp
from pathlib import Path


@dataclass
class Lesson:
    time: str
    discipline: str
    lecturers: str
    classroom: str
    week_code: str


class ScheduleParser:
    XML_URL = "https://voenmeh.ru/wp-content/themes/Avada-Child-Theme-Voenmeh/_voenmeh_grafics/TimetableGroup50.xml"

    @staticmethod
    async def download_current_xml():
        async with aiohttp.ClientSession() as session:
            async with session.get(ScheduleParser.XML_URL) as resp:
                if resp.status == 200:
                    content_bytes = await resp.read()
                    with open("../schedule.xml", "wb") as f:
                        f.write(content_bytes)
                    print("XML успешно скачан с сайта")
                    return True
                else:
                    print(f"Ошибка скачивания: статус {resp.status}")
                    return False

    def __init__(self, xml_path: str):
        self.xml_path = Path(xml_path)
        self.groups: Dict[str, Dict[str, Dict[str, List[Lesson]]]] = {}
        self._parse()

    def _parse(self) -> None:
        tree = ET.parse(self.xml_path)
        root = tree.getroot()

        for group_elem in root.findall('Group'):
            group_number = group_elem.get('Number')
            if not group_number:
                continue
            if group_number not in self.groups:
                self.groups[group_number] = {}

            for day_elem in group_elem.findall('Days/Day'):
                weekday = day_elem.get('Title')
                if not weekday:
                    continue
                if weekday not in self.groups[group_number]:
                    self.groups[group_number][weekday] = {'1': [], '2': []}

                for lesson_elem in day_elem.findall('GroupLessons/Lesson'):
                    week_code = lesson_elem.findtext('WeekCode', '').strip()
                    if week_code not in ('1', '2'):
                        continue
                    time = lesson_elem.findtext('Time', '').strip()
                    discipline = lesson_elem.findtext('Discipline', '').strip()

                    lecturers_elem = lesson_elem.find('Lecturers')
                    lecturers_names = []
                    if lecturers_elem is not None:
                        for lecturer in lecturers_elem.findall('Lecturer'):
                            short_name = lecturer.findtext('ShortName', '').strip()
                            if short_name:
                                lecturers_names.append(short_name)
                    lecturers_str = ', '.join(lecturers_names)
                    classroom = lesson_elem.findtext('Classroom', '').strip()

                    lesson = Lesson(
                        time=time,
                        discipline=discipline,
                        lecturers=lecturers_str,
                        classroom=classroom,
                        week_code=week_code
                    )
                    self.groups[group_number][weekday][week_code].append(lesson)

        self._parse_period(root)

    def _parse_period(self, root) -> None:
        period = root.find('Period')
        if period is not None:
            year = int(period.get('StartYear', 2026))
            month = int(period.get('StartMonth', 2))
            day = int(period.get('StartDay', 9))
            self.semester_start = date(year, month, day)
        else:
            self.semester_start = date(2026, 2, 9)

    def get_current_week_type(self) -> str:
        if not hasattr(self, 'semester_start'):
            return '1'
        today = date.today()
        delta = (today - self.semester_start).days
        if delta < 0:
            return '1'
        week_num = delta // 7
        return '1' if week_num % 2 == 0 else '2'

    def get_schedule(self, group_number: str, weekday: str, week_type: str) -> List[Lesson]:
        try:
            return self.groups[group_number][weekday].get(week_type, [])
        except KeyError:
            return []

    def get_available_groups(self) -> List[str]:
        return list(self.groups.keys())

    async def update_database(self):
        print(f"[{datetime.now()}] Обновление базы данных...")
        await db.clear_lessons_table()
        lessons_to_insert = []

        for group_number, days_dict in self.groups.items():
            for day_name, week_types in days_dict.items():
                for week_type, lessons in week_types.items():
                    for lesson in lessons:
                        time_start_str = lesson.time.split()[0]
                        h, m = map(int, time_start_str.split(':'))
                        total_minutes = h * 60 + m + 90
                        end_h = total_minutes // 60
                        end_m = total_minutes % 60
                        time_end_str = f"{end_h}:{end_m:02d}"

                        lesson_data = {
                            'group_number': group_number,
                            'day_of_week': day_name,
                            'week_type': week_type,
                            'time_start': time_start_str,
                            'time_end': time_end_str,
                            'discipline': lesson.discipline,
                            'lecturer_name': lesson.lecturers,
                            'classroom': lesson.classroom,
                        }
                        lessons_to_insert.append(lesson_data)

        if lessons_to_insert:
            await db.insert_many_lessons(lessons_to_insert)

        await db.set_last_update_time()
        print(f"[{datetime.now()}] Обновление базы данных завершено. Добавлено {len(lessons_to_insert)} занятий")


async def load_schedule_async(xml_path: str) -> ScheduleParser:
    loop = asyncio.get_running_loop()
    parser = await loop.run_in_executor(None, ScheduleParser, xml_path)
    return parser

