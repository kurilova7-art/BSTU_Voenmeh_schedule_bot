import asyncio, os
from aiogram import Bot
from dotenv import load_dotenv
from utils.schedule_parser import load_schedule_async, ScheduleParser
import bot_data

load_dotenv()
ADMIN_ID = int(os.getenv("ADMIN_ID"))

async def update_schedule_and_db(bot_instance: Bot):
    if not await ScheduleParser.download_current_xml():
        await bot_instance.send_message(ADMIN_ID, "❌ Ошибка загрузки расписания с сайта")
        return
    try:
        new_parser = await load_schedule_async("../schedule.xml")
        await new_parser.update_database()
        bot_data.schedule_parser = new_parser
    except Exception as e:
        await bot_instance.send_message(ADMIN_ID, f"❌ Ошибка при обновлении расписания: {e}")


async def start_scheduler(bot: Bot, interval_minutes: int = 60):
    while True:
        await asyncio.sleep(interval_minutes * 60)
        await update_schedule_and_db(bot)

