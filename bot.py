from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from google_api import get_gsheet_data
import os
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram import F, Router
from aiogram.types import Message
from aiogram.filters import Command


from aiogram.client.default import DefaultBotProperties

bot = Bot(
    token=os.getenv("BOT_TOKEN"),
    default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
)
dp = Dispatcher(storage=MemoryStorage())

webapp_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(
        text="🎬 Відкрити кіно-застосунок",
        web_app=WebAppInfo(url="https://lyuda140707.github.io/kinobot-webapp/")
    )]
])


@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer(
        "Привіт! Натисни кнопку нижче, щоб відкрити кіно-застосунок:",
        reply_markup=webapp_keyboard
    )

@dp.message(F.video)
async def get_file_id(message: types.Message):
    file_id = message.video.file_id
    await message.answer(f"`file_id` збережено:\n<code>{file_id}</code>", parse_mode="HTML")



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
