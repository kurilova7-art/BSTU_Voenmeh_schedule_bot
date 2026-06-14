from os import getenv
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from dotenv import load_dotenv
from handlers.routes import router
from utils.schedule_parser import load_schedule_async, ScheduleParser
import bot_data
from utils import database as db, scheduler
from aiogram.types import BotCommand

load_dotenv()
TOKEN = getenv("BOT_TOKEN")

dp = Dispatcher()
dp.include_router(router)


async def set_commands(bot: Bot):
    commands = [
        BotCommand(command="search", description="Поиск по группе, преподавателю, аудитории"),
        BotCommand(command="group", description="Поиск по группе"),
        BotCommand(command="teacher", description="Поиск по преподавателю"),
        BotCommand(command="classroom", description="Поиск по аудитории"),
        BotCommand(command="help", description="Помощь"),
        BotCommand(command="about", description="О боте"),
    ]
    await bot.set_my_commands(commands)


async def main():
    await db.init_db()
    if not await ScheduleParser.download_current_xml():
        print("Не удалось скачать расписание, используется локальный файл")
    parser = await load_schedule_async("schedule.xml")
    bot_data.schedule_parser = parser
    await parser.update_database()
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await set_commands(bot)
    asyncio.create_task(scheduler.start_scheduler(bot, 60))
    print("Проект запущен")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())