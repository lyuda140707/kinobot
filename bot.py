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
from aiogram import types


def clean_expired_pro():
    service = get_google_service()
    sheet = service.spreadsheets()

    req = sheet.values().get(
        spreadsheetId=os.getenv("SHEET_ID"),
        range="PRO!A2:D1000"
    ).execute()
    rows = req.get("values", [])
    cleared = 0

    for i, row in enumerate(rows):
        if len(row) < 4:
            continue
        expire_date = row[3]
        try:
            expire_dt = datetime.strptime(expire_date, "%Y-%m-%d")
        except Exception:
            continue
        if expire_dt.date() < datetime.now().date():
            row_number = i + 2
            sheet.values().update(
                spreadsheetId=os.getenv("SHEET_ID"),
                range=f"PRO!C{row_number}",
                valueInputOption="RAW",
                body={"values":[["Не активовано"]]}
            ).execute()
            cleared += 1
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


async def safe_send_admin(bot, admin_id, text, **kwargs):
    try:
        await bot.send_message(admin_id, text, **kwargs)
        return True
    except Exception as e:
        print(f"❗ Не вдалося надіслати повідомлення адміну {admin_id}: {e}")
        return False


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
    if len(args) != 2 or not args[1].isdigit():
        await message.reply("⚠️ Формат: /ok user_id")
        return

    user_id = args[1].strip()
    service = get_google_service()
    sheet = service.spreadsheets()
    spreadsheet_id = os.getenv("SHEET_ID")

    expire_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")

    # Отримати всі записи
    res = sheet.values().get(
        spreadsheetId=spreadsheet_id,
        range="PRO!A2:D1000"
    ).execute()
    rows = res.get("values", [])

    # Знайти всі рядки з цим user_id
    matched_rows = [(i + 2, row) for i, row in enumerate(rows) if len(row) >= 1 and row[0] == user_id]

    if matched_rows:
        # Оновлюємо перший, решту чистимо
        for idx, (row_number, row) in enumerate(matched_rows):
            if idx == 0:
                username = row[1] if len(row) > 1 else ""
                sheet.values().update(
                    spreadsheetId=spreadsheet_id,
                    range=f"PRO!A{row_number}:D{row_number}",
                    valueInputOption="USER_ENTERED",
                    body={"values": [[user_id, username, "Активно", expire_date]]}
                ).execute()
            else:
                # Очистити дублі
                sheet.values().update(
                    spreadsheetId=spreadsheet_id,
                    range=f"PRO!A{row_number}:D{row_number}",
                    valueInputOption="RAW",
                    body={"values": [["", "", "", ""]]}
                ).execute()
    else:
        # Якщо запису нема — додаємо
        sheet.values().append(
            spreadsheetId=spreadsheet_id,
            range="PRO!A2:D2",
            valueInputOption="USER_ENTERED",
            body={"values": [[user_id, "", "Активно", expire_date]]}
        ).execute()

    await message.reply(f"✅ PRO активовано для {user_id} до {expire_date}")

    try:
        await bot.send_message(
            chat_id=int(user_id),
            text=f"🎉 Ваш PRO доступ активовано до {expire_date}! Дякуємо за підтримку 💛"
        )
    except Exception as e:
        print(f"⚠️ Не вдалося надіслати повідомлення користувачу {user_id}: {e}")





from google_api import find_film_by_name

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    if message.text and len(message.text.split()) > 1:
        query = message.text.split(maxsplit=1)[1].strip()
    else:
        query = None

    if query:
        print(f"🔍 Отримано запит: {query}")

        film = find_film_by_name(query)
        if film:
            name = film.get("Назва", "Без назви")
            desc = film.get("Опис", "Без опису")
            file_id = film.get("file_id")
            caption = f"*🎬 {name}*\n{desc}"

            print(f"✅ Надсилаємо фільм: {name}")
            print(f"🎞 file_id: {file_id}")

            if file_id:
                try:
                    await bot.send_video(
                        chat_id=message.chat.id,
                        video=file_id,
                        caption=caption,
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    print(f"❌ Помилка надсилання відео: {e}")
                    await safe_send(bot, message.chat.id, "⚠️ Не вдалося надіслати відео")
            else:
                await message.answer(caption, parse_mode="Markdown")
        else:
            await safe_send(bot, message.chat.id, "Фільм не знайдено 😢")
    else:
        await safe_send(bot, message.chat.id, "☕ Хочеш трохи відпочити? Натискай кнопку — усе вже готово!", reply_markup=webapp_keyboard)



@dp.message(F.video)
async def get_file_id(message: types.Message):
    file_id = message.video.file_id
    await message.answer(f"🎥 file_id:\n<code>{file_id}</code>", parse_mode="HTML")






@dp.message(F.text)
async def process_message(message: types.Message):
    # --- /reply (відповідь адміну)
    if message.text and message.text.startswith('/reply '):
        parts = message.text.split(' ', 2)
        if len(parts) < 3:
            await message.reply("❗ Формат: /reply user_id відповідь", parse_mode=None)
            return
        user_id = parts[1]
        reply_text = parts[2]
        try:
            await bot.send_message(user_id, f"Відповідь від адміністратора:\n\n{reply_text}", parse_mode=None)
            await message.reply("✅ Відповідь надіслана користувачу.")
        except Exception as e:
            await message.reply(f"❗ Не вдалося надіслати відповідь: {e}")
        return  # Щоб не шукати далі як фільм

    # --- Пошук фільму
    if not message.text:
        return

    if not message.chat or not message.chat.id:
        print("❌ Немає message.chat.id — не надсилаємо відео")
        return

    query = message.text.strip()  # Можна .lower() — але find_film_by_name вже це робить

    film = find_film_by_name(query)

    if film:
        name = film.get("Назва", "Без назви")
        desc = film.get("Опис", "Без опису")
        file_id = film.get("file_id")

        caption = f"*🎬 {name}*\n{desc}"
        print(f"✅ Надсилаємо фільм: {name}")
        print(f"🎞 file_id: {file_id}")

        if file_id:
            try:
                await bot.send_video(
                    chat_id=message.chat.id,
                    video=file_id,
                    caption=caption,
                    parse_mode="Markdown"
                )
            except Exception as e:
                print(f"❌ Помилка надсилання відео: {e}")
                await safe_send(bot, message.chat.id, "⚠️ Не вдалося надіслати відео")
        else:
            await message.answer(caption, parse_mode="Markdown")
        return

    await safe_send(bot, message.chat.id, "Фільм не знайдено 😢")
