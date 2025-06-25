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
from google_api import get_google_service
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

def add_blocked_user(user_id: int):
    service = get_google_service()
    sheet = service.spreadsheets()
    sheet.values().append(
        spreadsheetId=os.getenv("SHEET_ID"),
        range="Заблокували!A2",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": [[str(user_id)]]}
    ).execute()
    print(f"🛑 Додано до таблиці Заблокували: {user_id}")

async def safe_send(bot: Bot, user_id: int, text: str, **kwargs):
    try:
        await bot.send_message(chat_id=user_id, text=text, **kwargs)
        return True
    except TelegramForbiddenError:
        print(f"❌ Користувач {user_id} заблокував бота")
        add_blocked_user(user_id)
    except TelegramBadRequest as e:
        print(f"❌ BadRequest {user_id}: {e}")
    except Exception as e:
        print(f"❌ Інша помилка {user_id}: {e}")
    return False
    

bot = Bot(
    token=os.getenv("BOT_TOKEN"),
    default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
)
dp = Dispatcher(storage=MemoryStorage())

webapp_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(
        text="🛋 Відкрити застосунок",
        web_app=WebAppInfo(url="https://lyuda140707.github.io/kinobot-webapp/")
    )]
])


@dp.message(Command("webapp"))
async def send_webapp(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="😎 Відкрити WebApp",
            web_app=WebAppInfo(url="https://lyuda140707.github.io/kinobot-webapp/")
        )]
    ])
    await message.answer("Ось кнопка для відкриття WebApp:", reply_markup=keyboard)


@dp.message(Command("start"))
async def start_handler(message: types.Message):
    if message.text and len(message.text.split()) > 1:
        query = message.text.split(maxsplit=1)[1]
    else:
        query = None

    if query:
        print(f"🔍 Отримано запит: {query}")
        films = get_gsheet_data()
        for film in films:
            if query.lower() in film.get("Назва", "").lower() or query.lower() in film.get("Опис", "").lower():
                name = film["Назва"]
                desc = film["Опис"]
                file_id = film.get("file_id")
                caption = f"*🎬 {name}*\n{desc}"

                print(f"✅ Надсилаємо фільм: {name}")
                print(f"🎞 file_id: {file_id}")

                if file_id:
                    await message.answer_video(file_id, caption=caption, parse_mode="Markdown")
                else:
                    await message.answer(caption, parse_mode="Markdown")
                return
        await safe_send(bot, message.chat.id, "Фільм не знайдено 😢")
    else:
        await safe_send(bot, message.chat.id, "☕ Хочеш трохи відпочити? Натискай кнопку — усе вже готово!", reply_markup=webapp_keyboard)


@dp.message(F.video)
async def get_file_id(message: types.Message):
    file_id = message.video.file_id
    await message.answer(f"🎥 file_id:\n<code>{file_id}</code>", parse_mode="HTML")

@dp.message(F.text)
async def search_film(message: types.Message):
    if not message.text:
        return

    query = message.text.lower()
    films = get_gsheet_data()

    for film in films:
        if query in film["Назва"].lower():
            name = film.get("Назва", "Без назви")
            desc = film.get("Опис", "Без опису")
            file_id = film.get("file_id")

            caption = f"*🎬 {name}*\n{desc}"
            print(f"✅ Надсилаємо фільм: {name}")
            print(f"🎞 file_id: {file_id}")

            if file_id:
                await message.answer_video(file_id, caption=caption, parse_mode="Markdown")
            else:
                await message.answer(caption, parse_mode="Markdown")
            return

    await safe_send(bot, message.chat.id, "Фільм не знайдено 😢")

    
  
