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
from google_api import add_user_if_not_exists
from aiogram.types import Message
MEDIA_CHANNEL_ID = int(os.getenv("MEDIA_CHANNEL_ID"))


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
async def activate_pro(message: Message):
    args = message.text.strip().split()
    if len(args) != 2:
        await message.reply("⚠️ Вкажи ID користувача: /ok 123456789")
        return

    user_id = args[1].strip()
    if not user_id.isdigit():
        await message.reply("❌ Некоректний ID")
        return

    service = get_google_service()
    sheet = service.spreadsheets()
    kyiv = timezone("Europe/Kyiv")
    now = datetime.now(kyiv)
    expire = now + timedelta(days=30)
    expire_str = expire.strftime("%Y-%m-%d")

    # Зчитуємо всі рядки з таблиці
    res = sheet.values().get(
        spreadsheetId=os.getenv("SHEET_ID"),
        range="PRO!A2:D1000"
    ).execute()

    rows = res.get("values", [])

    for idx, row in enumerate(rows, start=2):
        if len(row) < 1:
            continue

        sheet_user_id = str(row[0]).split('.')[0]  # <- ось тут ключ
        if sheet_user_id != user_id:
            continue

        username = row[1] if len(row) > 1 else ""

        sheet.values().update(
            spreadsheetId=os.getenv("SHEET_ID"),
            range=f"PRO!A{idx}:D{idx}",
            valueInputOption="RAW",
            body={"values": [[user_id, username, "Активно", expire_str]]}
        ).execute()

        await message.reply(f"✅ PRO активовано для {user_id} до {expire_str}")
        return

    await message.reply("❌ Користувача не знайдено в таблиці")
from google_api import find_film_by_name

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    # ————— 1) Записуємо користувача в Google Sheets —————
    add_user_if_not_exists(
        user_id=message.from_user.id,
        username=message.from_user.username or "",
        first_name=message.from_user.first_name or ""
    )

    # ————— 2) Далі ваша існуюча логіка —————
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
            message_id = film.get("message_id")
            caption = f"*🎬 {name}*\n{desc}"

            print(f"✅ Надсилаємо фільм: {name}")
            print(f"🆔 message_id: {message_id}")

            if message_id:
                try:
                    await bot.copy_message(
                        chat_id=message.chat.id,
                        from_chat_id=MEDIA_CHANNEL_ID,
                        message_id=int(message_id),
                        caption=caption,
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    print(f"❌ Помилка копіювання відео: {e}")
                    await safe_send(bot, message.chat.id, "⚠️ Не вдалося відправити відео")
            else:
                await message.answer(caption, parse_mode="Markdown")
        else:
            await safe_send(bot, message.chat.id, "Фільм не знайдено 😢")
    else:
        await safe_send(
            bot,
            message.chat.id,
            "☕ Хочеш трохи відпочити? Натискай кнопку — усе вже готово!",
            reply_markup=webapp_keyboard
        )


@dp.message(F.video)
async def get_file_id(message: types.Message):
    file_id = message.video.file_id
    await message.answer(f"🎥 file_id:\n<code>{file_id}</code>", parse_mode="HTML")






@dp.message(F.text)
async def process_message(message: types.Message):
    add_user_if_not_exists(
        user_id=message.from_user.id,
        username=message.from_user.username or "",
        first_name=message.from_user.first_name or ""
    )
    
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
        message_id = film.get("message_id")

        caption = f"*🎬 {name}*\n{desc}"
        print(f"✅ Надсилаємо фільм: {name}")
        print(f"🆔 message_id: {message_id}")

        if message_id:
            try:
                await bot.copy_message(
                    chat_id=message.chat.id,
                    from_chat_id=MEDIA_CHANNEL_ID,
                    message_id=int(message_id),
                    caption=caption,
                    parse_mode="Markdown"
                )
            except Exception as e:
                print(f"❌ Помилка копіювання відео: {e}")
                await safe_send(bot, message.chat.id, "⚠️ Не вдалося відправити відео")


        else:
            await message.answer(caption, parse_mode="Markdown")
        return

    await safe_send(bot, message.chat.id, "Фільм не знайдено 😢")
