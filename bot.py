from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from google_api import get_gsheet_data
import os

from aiogram.client.default import DefaultBotProperties

bot = Bot(
    token=os.getenv("BOT_TOKEN"),
    default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
)
dp = Dispatcher(storage=MemoryStorage())

@dp.message()
async def search_film(message: types.Message):
    films = get_gsheet_data()
    query = message.text.lower()

    for film in films:
        if query in film["Назва"].lower():
            name = film.get("Назва", "Без назви")
            desc = film.get("Опис", "Без опису")
            link = film.get("Посилання", "")

            text = f"*🎬 {name}*\n{desc}\n[Дивитись]({link})"
            await message.answer(text)
            return

    await message.answer("Фільм не знайдено 😢")
