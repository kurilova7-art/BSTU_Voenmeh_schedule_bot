from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton,
    CallbackQuery
)
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from datetime import datetime
import re
import html
from typing import List, Dict

import bot_data
import utils.database as db
from utils.schedule_parser import Lesson
from utils.storage import save_user_data

router = Router()


WEEKDAYS_RU = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота"]
WEEKDAYS_SHORT = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб"]


class SearchStates(StatesGroup):
    universal_search = State()
    group_search = State()
    teacher_search = State()
    classroom_search = State()
    choosing_lecturer = State()


# ---------- Вспомогательные функции ----------
def time_to_minutes(time_str: str) -> int:
    h, m = map(int, time_str.split(':'))
    return h * 60 + m


def format_time_range(time_str: str) -> str:
    match = re.match(r'(\d{1,2}:\d{2})', time_str)
    if not match:
        return time_str
    start = match.group(1)
    h, m = map(int, start.split(':'))
    total_minutes = h * 60 + m + 90
    end_h = total_minutes // 60
    end_m = total_minutes % 60
    end = f"{end_h}:{end_m:02d}"
    return f"{start} – {end}"


def get_current_day_index() -> int:
    today = datetime.today().weekday()
    if today == 6:
        return 0
    return today if today < 6 else 0


async def get_week_schedule_text(entity_type: str, entity_name: str, current_week_type: str) -> str:
    if entity_type == 'group':
        header = f"📅 Расписание для группы {html.escape(entity_name)} на неделю\n\n"
    elif entity_type == 'teacher':
        header = f"🎓 Расписание преподавателя {html.escape(entity_name)} на неделю\n\n"
    else:
        header = f"🏛 Занятия в аудитории {html.escape(entity_name)} на неделю\n\n"

    lines = [header]

    for day_index, day_name in enumerate(WEEKDAYS_RU):
        lines.append(f"<b>{day_name}</b>")

        if entity_type == 'group':
            lessons_odd = bot_data.schedule_parser.get_schedule(entity_name, day_name, '1')
            lessons_even = bot_data.schedule_parser.get_schedule(entity_name, day_name, '2')
            grouped = {}
            for week, lessons in (('1', lessons_odd), ('2', lessons_even)):
                for les in lessons:
                    key = (les.time, les.discipline)
                    if key not in grouped:
                        grouped[key] = {'week': week, 'extra': set()}
                    grouped[key]['extra'].add(f"{les.lecturers or '—'} {les.classroom or '—'}")
            pairs = []
            for (time_str, discipline), data in grouped.items():
                time_range = format_time_range(time_str)
                extra_str = ', '.join(sorted(data['extra']))
                pairs.append((time_range, discipline, extra_str, data['week']))
        else:
            if entity_type == 'teacher':
                lessons_odd = await db.search_lessons_by_lecturer_day_week(entity_name, day_name, '1')
                lessons_even = await db.search_lessons_by_lecturer_day_week(entity_name, day_name, '2')
            else:
                lessons_odd = await db.search_lessons_by_classroom_day_week(entity_name, day_name, '1')
                lessons_even = await db.search_lessons_by_classroom_day_week(entity_name, day_name, '2')

            grouped = {}
            for week, lessons in (('1', lessons_odd), ('2', lessons_even)):
                for les in lessons:
                    key = (les['time_start'], les['discipline'])
                    if key not in grouped:
                        grouped[key] = {'week': week, 'groups': set()}
                        if entity_type == 'teacher':
                            grouped[key]['extra'] = les['classroom'] or '—'
                        else:
                            grouped[key]['extra'] = les['lecturer_name'] or '—'
                    grouped[key]['groups'].add(les['group_number'])

            pairs = []
            for (time_str, discipline), data in grouped.items():
                time_range = format_time_range(time_str)
                groups_str = ', '.join(sorted(data['groups']))
                if entity_type == 'teacher':
                    extra_info = f"{groups_str}  {data['extra']}"
                else:
                    extra_info = f"{groups_str}  {data['extra']}"
                pairs.append((time_range, discipline, extra_info, data['week']))

        pairs.sort(key=lambda x: time_to_minutes(x[0].split('–')[0].strip()))

        if not pairs:
            lines.append("  📭 Пар нет\n")
        else:
            for time_range, discipline, extra, week in pairs:
                week_label = "нечёт" if week == '1' else "чёт"
                if week == current_week_type:
                    lines.append(f"  ✨ {time_range}  {discipline}  {extra}  <i>({week_label})</i>")
                else:
                    lines.append(f"  • {time_range}  {discipline}  {extra}  ({week_label})")
            lines.append("")

    return "\n".join(lines)


def get_schedule_text(group: str, day_index: int, week_type: str) -> str:
    day_name = WEEKDAYS_RU[day_index]
    lessons = bot_data.schedule_parser.get_schedule(group, day_name, week_type)
    lessons = sorted(lessons, key=lambda l: time_to_minutes(l.time.split()[0]))
    if not lessons:
        pairs_text = "📭 Пар нет, самое время отдохнуть"
    else:
        lines = []
        for les in lessons:
            time_range = format_time_range(les.time)
            lines.append(
                f"📚 <b>{html.escape(time_range)}</b>\n"
                f"{html.escape(les.discipline)}\n"
                f"{html.escape(les.lecturers or '—')}  {html.escape(les.classroom or '—')}"
            )
        pairs_text = "\n\n".join(lines)
    week_name = "Нечётная" if week_type == "1" else "Чётная"
    return (f"📅 Расписание для группы {html.escape(group)}\n\n"
            f"<b>{html.escape(day_name)}</b> ({week_name} неделя)\n\n{pairs_text}")


async def get_teacher_schedule_text(teacher_name: str, day_index: int, week_type: str) -> str:
    day_name = WEEKDAYS_RU[day_index]
    lessons = await db.search_lessons_by_lecturer_day_week(teacher_name, day_name, week_type)
    lessons = sorted(lessons, key=lambda l: time_to_minutes(l['time_start']))
    if not lessons:
        pairs_text = "📭 Пар нет, хорошего дня!"
    else:
        grouped = {}
        for les in lessons:
            key = (les['time_start'], les['discipline'])
            if key not in grouped:
                grouped[key] = {'groups': set(), 'classroom': les['classroom'], 'time_start': les['time_start']}
            grouped[key]['groups'].add(les['group_number'])
        lines = []
        for (time_start, discipline), data in grouped.items():
            time_range = format_time_range(time_start)
            groups_str = ', '.join(sorted(data['groups']))
            lines.append(
                f"📚 <b>{html.escape(time_range)}</b>\n"
                f"{html.escape(discipline)}\n"
                f"{html.escape(groups_str)}  {html.escape(data['classroom'] or '—')}"
            )
        pairs_text = "\n\n".join(lines)
    week_name = "Нечётная" if week_type == "1" else "Чётная"
    return (f"🎓 <b>Расписание преподавателя {html.escape(teacher_name)}</b>\n\n"
            f"<b>{html.escape(day_name)}</b> ({week_name} неделя)\n\n{pairs_text}")


async def get_classroom_schedule_text(classroom: str, day_index: int, week_type: str) -> str:
    day_name = WEEKDAYS_RU[day_index]
    lessons = await db.search_lessons_by_classroom_day_week(classroom, day_name, week_type)
    lessons = sorted(lessons, key=lambda l: time_to_minutes(l['time_start']))
    if not lessons:
        pairs_text = "📭 Пар нет, хорошего дня!"
    else:
        grouped = {}
        for les in lessons:
            key = (les['time_start'], les['discipline'])
            if key not in grouped:
                grouped[key] = {'groups': set(), 'lecturers': set()}
            grouped[key]['groups'].add(les['group_number'])
            grouped[key]['lecturers'].add(les['lecturer_name'])
        lines = []
        for (time_start, discipline), data in grouped.items():
            time_range = format_time_range(time_start)
            groups_str = ', '.join(sorted(data['groups']))
            lecturers_str = ', '.join(sorted(data['lecturers']))
            lines.append(
                f"📚 <b>{html.escape(time_range)}</b>\n"
                f"{html.escape(discipline)}\n"
                f"{html.escape(groups_str)}  {html.escape(lecturers_str)}"
            )
        pairs_text = "\n\n".join(lines)
    week_name = "Нечётная" if week_type == "1" else "Чётная"
    return (f"🏛 <b>Занятия в аудитории {html.escape(classroom)}</b>\n\n"
            f"<b>{html.escape(day_name)}</b> ({week_name} неделя)\n\n{pairs_text}")


def get_schedule_keyboard(day_index: int, week_type: str) -> InlineKeyboardMarkup:
    row1 = [
        InlineKeyboardButton(text="◀️", callback_data="nav_prev"),
        InlineKeyboardButton(text="Сегодня", callback_data="nav_today"),
        InlineKeyboardButton(text="▶️", callback_data="nav_next")
    ]
    week_1_text = "Нечётная" + ("✓" if week_type == "1" else "")
    week_2_text = "Чётная" + ("✓" if week_type == "2" else "")
    row2 = [
        InlineKeyboardButton(text="Неделя", callback_data="week_view"),
        InlineKeyboardButton(text=week_1_text, callback_data="set_week_1"),
        InlineKeyboardButton(text=week_2_text, callback_data="set_week_2")
    ]
    row3 = []
    for i, short in enumerate(WEEKDAYS_SHORT):
        marker = "✓" if i == day_index else ""
        row3.append(InlineKeyboardButton(text=f"{marker}{short}", callback_data=f"set_day_{i}"))
    return InlineKeyboardMarkup(inline_keyboard=[row1, row2, row3])


def split_long_message(text: str, limit: int = 4000) -> List[str]:
    parts = []
    current_part = ""
    for line in text.split('\n'):
        if len(current_part) + len(line) + 1 > limit:
            parts.append(current_part)
            current_part = line
        else:
            current_part += ('\n' + line) if current_part else line
    if current_part:
        parts.append(current_part)
    return parts


# ---------- Сохранение состояния ----------
def save_state(chat_id: int):
    save_user_data(bot_data.user_states)


def update_user_state(chat_id: int, entity_type: str, entity_name: str, day_index: int, week_type: str, week_mode: bool = False):
    bot_data.user_states[chat_id] = {
        'entity': {'type': entity_type, 'name': entity_name},
        'day_index': day_index,
        'week_type': week_type,
        'week_mode': week_mode
    }
    save_state(chat_id)


# ---------- Поиск по группе ----------
@router.message(Command("group"))
async def cmd_group_search(message: Message, state: FSMContext):
    await message.answer("Введите номер группы (например, 09С31):", parse_mode="Markdown")
    await state.set_state(SearchStates.group_search)


@router.message(SearchStates.group_search)
async def process_group_search(message: Message, state: FSMContext):
    group = message.text.strip().upper()
    if bot_data.schedule_parser is None:
        await message.answer("Расписание ещё не загружено")
        await state.clear()
        return
    available = bot_data.schedule_parser.get_available_groups()
    if group not in available:
        await message.answer(f"Группа {group} не найдена. Попробуйте ещё раз.")
        await state.clear()
        return
    current_day = get_current_day_index()
    current_week = bot_data.schedule_parser.get_current_week_type()
    update_user_state(message.chat.id, 'group', group, current_day, current_week)
    text = get_schedule_text(group, current_day, current_week)
    keyboard = get_schedule_keyboard(current_day, current_week)
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    await state.clear()


# ---------- Поиск по преподавателю ----------
@router.message(Command("teacher"))
async def cmd_teacher_search(message: Message, state: FSMContext):
    await message.answer("Введите фамилию преподавателя:", parse_mode="Markdown")
    await state.set_state(SearchStates.teacher_search)


@router.message(SearchStates.teacher_search)
async def process_teacher_search(message: Message, state: FSMContext):
    query = message.text.strip().title()
    all_lecturers = await db.get_all_lecturers()
    matching = [l for l in all_lecturers if query.lower() in l.lower()]
    if not matching:
        await message.answer(f"❌ Преподаватель *{query}* не найден.", parse_mode="Markdown")
        await state.clear()
        return
    if len(matching) == 1:
        teacher = matching[0]
        current_day = get_current_day_index()
        current_week = bot_data.schedule_parser.get_current_week_type()
        update_user_state(message.chat.id, 'teacher', teacher, current_day, current_week)
        text = await get_teacher_schedule_text(teacher, current_day, current_week)
        keyboard = get_schedule_keyboard(current_day, current_week)
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        await state.clear()
    else:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=l, callback_data=f"teacher_choose_{l}")] for l in matching
        ])
        await message.answer("Найдено несколько преподавателей. Уточните:", reply_markup=keyboard)
        await state.set_state(SearchStates.choosing_lecturer)


@router.callback_query(lambda c: c.data.startswith("teacher_choose_"))
async def process_teacher_choice(callback: CallbackQuery, state: FSMContext):
    teacher = callback.data.split("teacher_choose_", 1)[1]
    current_day = get_current_day_index()
    current_week = bot_data.schedule_parser.get_current_week_type()
    update_user_state(callback.message.chat.id, 'teacher', teacher, current_day, current_week)
    text = await get_teacher_schedule_text(teacher, current_day, current_week)
    keyboard = get_schedule_keyboard(current_day, current_week)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()
    await state.clear()


# ---------- Поиск по аудитории ----------
@router.message(Command("classroom"))
async def cmd_classroom_search(message: Message, state: FSMContext):
    await message.answer("Введите номер аудитории (например, 468*):")
    await state.set_state(SearchStates.classroom_search)


@router.message(SearchStates.classroom_search)
async def process_classroom_search(message: Message, state: FSMContext):
    query = message.text.strip()
    lessons = await db.search_lessons_by_classroom(query)
    if not lessons:
        await message.answer(f"❌ Аудитория <b>{query}</b> не найдена.", parse_mode="HTML")
        await state.clear()
        return
    current_day = get_current_day_index()
    current_week = bot_data.schedule_parser.get_current_week_type()
    update_user_state(message.chat.id, 'classroom', query, current_day, current_week)
    text = await get_classroom_schedule_text(query, current_day, current_week)
    keyboard = get_schedule_keyboard(current_day, current_week)
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    await state.clear()


# ---------- Универсальный поиск ----------
@router.message(Command("search"))
async def cmd_search(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("🔍 *Введите что-то одно: *\n\n"
                         "• Номер группы \n"
                         "• Фамилию преподавателя \n"
                         "• Номер аудитории ",
                         parse_mode="Markdown")
    await state.set_state(SearchStates.universal_search)


@router.message(SearchStates.universal_search)
async def process_universal_search(message: Message, state: FSMContext):
    query = message.text.strip()
    groups_found = [g for g in bot_data.schedule_parser.get_available_groups() if query.upper() == g.upper()]
    if groups_found:
        if len(groups_found) == 1:
            group = groups_found[0]
            current_day = get_current_day_index()
            current_week = bot_data.schedule_parser.get_current_week_type()
            update_user_state(message.chat.id, 'group', group, current_day, current_week)
            text = get_schedule_text(group, current_day, current_week)
            keyboard = get_schedule_keyboard(current_day, current_week)
            await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
            await state.clear()
            return
        else:
            await message.answer("Найдено несколько групп: " + ", ".join(groups_found))
            await state.clear()
            return

    all_lecturers = await db.get_all_lecturers()
    matching_lecturers = [l for l in all_lecturers if query.lower() in l.lower()]
    if matching_lecturers:
        if len(matching_lecturers) == 1:
            teacher = matching_lecturers[0]
            current_day = get_current_day_index()
            current_week = bot_data.schedule_parser.get_current_week_type()
            update_user_state(message.chat.id, 'teacher', teacher, current_day, current_week)
            text = await get_teacher_schedule_text(teacher, current_day, current_week)
            keyboard = get_schedule_keyboard(current_day, current_week)
            await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
            await state.clear()
            return
        else:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=l, callback_data=f"teacher_choose_{l}")] for l in matching_lecturers
            ])
            await message.answer("Найдено несколько преподавателей. Уточните:", reply_markup=keyboard)
            await state.set_state(SearchStates.choosing_lecturer)
            return

    classroom_lessons = await db.search_lessons_by_classroom(query)
    if classroom_lessons:
        current_day = get_current_day_index()
        current_week = bot_data.schedule_parser.get_current_week_type()
        update_user_state(message.chat.id, 'classroom', query, current_day, current_week)
        text = await get_classroom_schedule_text(query, current_day, current_week)
        keyboard = get_schedule_keyboard(current_day, current_week)
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        await state.clear()
        return

    await message.answer("По вашему запросу ничего не найдено. Попробуйте ещё раз.")
    await state.clear()


# ---------- Навигация по календарю ----------
@router.callback_query(F.data == "week_view")
async def week_view(callback: CallbackQuery):
    await callback.answer()
    chat_id = callback.message.chat.id
    state = bot_data.user_states.get(chat_id)
    if not state:
        await callback.message.answer("Сначала выберите группу, преподавателя или аудиторию.")
        return
    state['week_mode'] = True
    save_state(chat_id)
    entity = state['entity']
    real_week = bot_data.schedule_parser.get_current_week_type()
    text = await get_week_schedule_text(entity['type'], entity['name'], real_week)
    keyboard = get_schedule_keyboard(state['day_index'], state['week_type'])

    if len(text) > 4000:
        parts = split_long_message(text)
        await callback.message.edit_text(parts[0], reply_markup=keyboard, parse_mode="HTML")
        for part in parts[1:]:
            await callback.message.answer(part, parse_mode="HTML")
    else:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data.startswith(("nav_", "set_week_", "set_day_")))
async def schedule_navigation(callback: CallbackQuery):
    await callback.answer()
    chat_id = callback.message.chat.id
    state = bot_data.user_states.get(chat_id)
    if not state:
        await callback.message.answer("Сначала выберите группу, преподавателя или аудиторию.")
        return
    if bot_data.schedule_parser is None:
        await callback.message.answer("Расписание недоступно")
        return

    old_day = state['day_index']
    old_week = state['week_type']
    data = callback.data
    if data == "nav_prev":
        new_day = (old_day - 1) % 6
        new_week = old_week
    elif data == "nav_next":
        new_day = (old_day + 1) % 6
        new_week = old_week
    elif data == "nav_today":
        new_day = get_current_day_index()
        new_week = old_week
    elif data.startswith("set_week_"):
        new_week = data.split("_")[2]
        new_day = old_day
    elif data.startswith("set_day_"):
        new_day = int(data.split("_")[2])
        new_week = old_week
    else:
        return

    if new_day == old_day and new_week == old_week:
        return

    state['day_index'] = new_day
    state['week_type'] = new_week
    was_week_mode = state.get('week_mode', False)
    if was_week_mode:
        state['week_mode'] = False
    save_state(chat_id)

    entity = state['entity']
    if entity['type'] == 'group':
        text = get_schedule_text(entity['name'], new_day, new_week)
    elif entity['type'] == 'teacher':
        text = await get_teacher_schedule_text(entity['name'], new_day, new_week)
    else:
        text = await get_classroom_schedule_text(entity['name'], new_day, new_week)

    keyboard = get_schedule_keyboard(new_day, new_week)
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:
        print(f"Ошибка при обновлении сообщения: {e}")


# ---------- Старт, помощь, о боте ----------
@router.message(Command("start"))
@router.message(F.text.lower() == "старт")
async def start(message: Message, state: FSMContext):
    await cmd_search(message, state)


@router.message(Command("help"))
@router.message(F.text.lower() == "помощь")
async def help(message: Message):
    await message.answer(
        "<b>Список команд:</b>\n"
        "✅ /about - о боте\n"
        "✅ /search - поиск по группе, преподавателю, аудитории\n"
        "✅ /group - поиск по группе\n"
        "✅ /teacher - поиск по преподавателю\n"
        "✅ /classroom - поиск по аудитории",
        parse_mode="HTML")


@router.message(Command("about"))
@router.message(F.text.lower() == "о боте")
async def about(message: Message):
    await message.answer(
        "<b>О боте</b>\n"
        "🔧 Бот написан на python 3.14\n"
        "🔧 Библиотеки: aiogram, dotenv, xml.etree.ElementTree\n"
        "🔧 Версия 0.0.1\n"
        "🔧 Не коммерческий проект\n"
        "🔧 <a href='https://voenmeh.ru/obrazovanie/timetables'>Ссылка на расписание с сайта</a>",
        parse_mode="HTML")


@router.message()
async def default(message: Message):
    await message.answer("Введите /help")

