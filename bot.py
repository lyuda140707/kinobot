from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from google_api import get_gsheet_data
import os
from dotenv import load_dotenv
load_dotenv()
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram import F
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
import logging

logging.basicConfig(level=logging.INFO)

bot = Bot(
    token=os.getenv("BOT_TOKEN"),
    default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
)
dp = Dispatcher(storage=MemoryStorage())

webapp_keyboard = InlineKeyboardMarkup(inline_keyboard=[  # Кнопка для WebApp
    [InlineKeyboardButton(
        text="🎬 Відкрити кіно-застосунок",
        web_app=WebAppInfo(url="https://lyuda140707.github.io/kinobot-webapp/")
    )]
])

back_to_menu_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[  # Кнопка для повернення в каталог
        [
            InlineKeyboardButton(
                text="🎥 Відкрити каталог фільмів",
                web_app=WebAppInfo(url="https://lyuda140707.github.io/kinobot-webapp/")
            )
        ]
    ]
)

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer("Привіт! Натисни кнопку нижче, щоб відкрити кіно-застосунок:", reply_markup=webapp_keyboard)

@dp.message(Command("webapp"))
async def send_webapp(message: types.Message):
    await message.answer("Ось кнопка для відкриття WebApp:", reply_markup=webapp_keyboard)

@dp.message()  # Замінили на обробку всіх повідомлень
async def handle_video_request(message: types.Message):
    # Отримуємо параметри з URL (user_id і file_id)
    command, user_id, file_id = message.text.split("_")

    # Якщо все коректно — надсилаємо фільм
    if user_id and file_id:
        await bot.send_video(
            chat_id=user_id,
            video=file_id,
            caption="🎬 Ось ваш фільм! Насолоджуйтесь переглядом! 🍿"
        )

@dp.message(F.video)
async def get_file_id(message: types.Message):
    file_id = message.video.file_id
    await message.answer(f"🎥 file_id:\n<code>{file_id}</code>", parse_mode="HTML")

