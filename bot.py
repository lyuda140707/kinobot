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
from datetime import datetime, timedelta


def clean_expired_pro():
    service = get_google_service()
    sheet = service.spreadsheets()

    req = sheet.values().get(
        spreadsheetId=os.getenv("SHEET_ID"),
        range="PRO!A2:C1000"
    ).execute()

    rows = req.get("values", [])
    cleared = 0

    for i, row in enumerate(rows):
        if len(row) < 3:
            continue

        user_id = row[0]
        status = row[1]
        expire_date = row[2]

        try:
            expire_dt = datetime.strptime(expire_date, "%Y-%m-%d")
            if expire_dt < datetime.now():
                row_number = i + 2
                sheet.values().update(
                    spreadsheetId=os.getenv("SHEET_ID"),
                    range=f"PRO!A{row_number}:C{row_number}",
                    valueInputOption="RAW",
                    body={"values": [["", "", ""]]}
                ).execute()
                cleared += 1
        except Exception as e:
            print(f"⚠️ Помилка обробки рядка {i+2}: {e}")

    print(f"✅ Очищено {cleared} прострочених записів")


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


@dp.message(Command("ok"))
async def approve_pro(message: types.Message):
    if message.from_user.id != 7963871119:  # свій ID
        return

    args = message.text.split()
    if len(args) != 2:
        await message.reply("⚠️ Формат: /ok user_id")
        return

    user_id = args[1].strip()  # прибираємо пробіли
    service = get_google_service()
    sheet = service.spreadsheets()

    expire_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")

    # Шукаємо користувача
    req = sheet.values().get(
        spreadsheetId=os.getenv("SHEET_ID"),
        range="PRO!A2:C1000"
    ).execute()

    rows = req.get("values", [])
    updated = False

    for i, row in enumerate(rows):
        if row and row[0] == user_id:
            row_number = i + 2
            sheet.values().update(
                spreadsheetId=os.getenv("SHEET_ID"),
                range=f"PRO!A{row_number}:C{row_number}",
                valueInputOption="USER_ENTERED",
                body={"values": [[user_id, "Активно", expire_date]]}
            ).execute()
            updated = True
            break

    if not updated:
        sheet.values().append(
            spreadsheetId=os.getenv("SHEET_ID"),
            range="PRO!A:C",
            valueInputOption="USER_ENTERED",
            body={"values": [[user_id, "Активно", expire_date]]}
        ).execute()

    await message.reply(f"✅ PRO активовано для {user_id} до {expire_date}")

    # Надсилаємо повідомлення користувачу
    try:
        await bot.send_message(
            chat_id=int(user_id),
            text=f"✅ Ваш PRO доступ активовано до {expire_date}! 🎬 Приємного перегляду!"
        )
    except Exception as e:
        print(f"❗ Не вдалося надіслати повідомлення користувачу {user_id}: {e}")




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

    
  
