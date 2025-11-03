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
MEDIA_CHANNEL_ID = int(os.getenv("MEDIA_CHANNEL_ID"))
import requests
import asyncio
import urllib.parse
# ⚙️ Отримує file_id з повідомлення в каналі за message_id
async def get_file_id_from_message(bot, channel_id: int, message_id: int):
    try:
        msg = await bot.forward_message(chat_id=8265377605, from_chat_id=channel_id, message_id=message_id)
        # ⛔️ одразу видаляємо, щоб користувачу не надсилало нічого
        await bot.delete_message(chat_id=8265377605, message_id=msg.message_id)
        if msg.video:
            return msg.video.file_id
    except Exception as e:
        print(f"⚠️ Не вдалося отримати file_id з message_id {message_id}: {e}")
    return None


SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY")


def _sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }


def sb_find_by_message_or_file(mid_or_fid: str):
    """Шукає фільм або за message_id, або за file_id"""
    q = urllib.parse.quote(mid_or_fid)
    url1 = f"{SUPABASE_URL}/rest/v1/films?select=*&message_id=eq.{q}&limit=1"
    url2 = f"{SUPABASE_URL}/rest/v1/films?select=*&file_id=eq.{q}&limit=1"

    for url in (url1, url2):
        r = requests.get(url, headers=_sb_headers(), timeout=10)
        if r.ok and r.json():
            return r.json()[0]
    return None
def sb_update_fileid_by_message_id(message_id: str, new_file_id: str):
    """Оновлює file_id у таблиці films за message_id (int8)"""
    import urllib.parse

    print(f"🧩 [DEBUG] sb_update_fileid_by_message_id викликано для message_id={message_id}, file_id={new_file_id}")
    try:
        msg_id_int = int(message_id)
        msg_q = urllib.parse.quote(str(msg_id_int))
        url = f"{SUPABASE_URL}/rest/v1/films?message_id=eq.{msg_q}"

        data = {"file_id": new_file_id}
        r = requests.patch(url, headers=_sb_headers(), json=data, timeout=10)

        if r.ok:
            print(f"✅ [Supabase] Оновлено file_id для message_id={msg_id_int}")
            return True
        else:
            print(f"⚠️ [Supabase] Помилка оновлення ({r.status_code}): {r.text}")
            return False
    except Exception as e:
        print(f"❌ [Supabase] Помилка при оновленні file_id: {e}")
        return False
def sb_update_telegram_url_by_file_id(file_id: str):
    """Отримує прямий CDN-лінк Telegram і зберігає його у колонку telegram_url"""
    import requests
    import os

    if not file_id or len(file_id) < 10:
        print("⚠️ Невірний file_id")
        return

    BOT_TOKEN = os.getenv("BOT_TOKEN")
    SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
    SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY")

    # 1️⃣ Отримуємо шлях до файлу
    info = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={file_id}").json()
    if not info.get("ok"):
        print(f"⚠️ Telegram не повернув file_path для {file_id}")
        return

    file_path = info["result"]["file_path"]
    cdn_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"

    # 2️⃣ Оновлюємо telegram_url у таблиці films
    url = f"{SUPABASE_URL}/rest/v1/films?file_id=eq.{file_id}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    payload = {"telegram_url": cdn_url}

    r = requests.patch(url, headers=headers, json=payload)
    if r.ok:
        print(f"✅ telegram_url записано у Supabase для file_id={file_id}")
    else:
        print(f"⚠️ Не вдалося записати telegram_url ({r.status_code}): {r.text}")


def sb_find_by_name_like(name: str):
    q = urllib.parse.quote(f"*{name}*")
    url = f"{SUPABASE_URL}/rest/v1/films?select=*&title=ilike.{q}&limit=50"
    r = requests.get(url, headers=_sb_headers(), timeout=10)
    r.raise_for_status()
    return r.json()



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
# === 📋 Реферальна система ===
def update_referrals(inviter_id: str, invited_id: str):
    """Оновлює таблицю 'Referrals' у Google Sheets."""
    service = get_google_service()
    sheet = service.spreadsheets()
    spreadsheet_id = os.getenv("SHEET_ID")

    # Зчитуємо всі рядки з аркуша Referrals
    res = sheet.values().get(
        spreadsheetId=spreadsheet_id,
        range="Referrals!A2:D1000"
    ).execute()
    rows = res.get("values", [])

    # Шукаємо запрошувача
    found_idx = None
    for i, row in enumerate(rows, start=2):
        if len(row) > 0 and row[0] == str(inviter_id):
            found_idx = i
            break

    if found_idx:
        invited_ids = []
        if len(rows[found_idx - 2]) > 1 and rows[found_idx - 2][1]:
            invited_ids = [x.strip() for x in rows[found_idx - 2][1].split(",") if x.strip()]
        if str(invited_id) not in invited_ids:
            invited_ids.append(str(invited_id))
            invited_count = len(invited_ids)
            sheet.values().update(
                spreadsheetId=spreadsheet_id,
                range=f"Referrals!B{found_idx}:D{found_idx}",
                valueInputOption="USER_ENTERED",
                body={"values": [[",".join(invited_ids), "", invited_count]]}
            ).execute()
            print(f"✅ Додано {invited_id} до запрошень {inviter_id}")
    else:
        # Якщо запрошувача немає — додаємо нового
        sheet.values().append(
            spreadsheetId=spreadsheet_id,
            range="Referrals!A2:D2",
            valueInputOption="USER_ENTERED",
            body={"values": [[str(inviter_id), str(invited_id), "FALSE", 1]]}
        ).execute()
        print(f"🆕 Новий рядок для {inviter_id} створено з першим запрошеним {invited_id}")
        # 🧭 Якщо вже 3 або більше — повідомляємо адміну
    try:
        invited_count_now = len(invited_ids) if found_idx else 1
        if invited_count_now >= 3:
            admin_id = 8265377605  # <-- заміни на свій Telegram ID, якщо інший
            bot_token = os.getenv("BOT_TOKEN")
            msg = f"🎯 Користувач {inviter_id} запросив {invited_count_now} друзів — готовий до PRO 🎁"
            requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage",
                          json={"chat_id": admin_id, "text": msg})
            print(f"📩 Повідомлення адміну: {msg}")
    except Exception as e:
        print(f"⚠️ Не вдалося надіслати повідомлення адміну: {e}")

    

bot = Bot(
    token=os.getenv("BOT_TOKEN"),
    default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
)
dp = Dispatcher(storage=MemoryStorage())

webapp_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(
        text="🛋 Відкрити застосунок",
        web_app=WebAppInfo(url="https://relaxbox.site/")
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
            web_app=WebAppInfo(url="https://relaxbox.site/")
        )]
    ])
    await message.answer("Ось кнопка для відкриття WebApp:", reply_markup=keyboard)


@dp.message(Command("ok"))
async def approve_pro(message: types.Message):
    print("✅ Стартував approve_pro")
    print(f"From user id: {message.from_user.id}, text: {message.text}")

    if message.from_user.id not in [8265377605, 7963871119]:
        print("⛔ Не твій адмінський ID, вихід.")
        return

    args = message.text.split()
    if len(args) != 2 or not args[1].isdigit():
        print("⛔ Некоректний формат команди")
        await message.reply("⚠️ Формат: <code>/ok user_id</code>", parse_mode="HTML")
        return

    user_id = args[1].strip()
    print(f"🔎 Шукаємо user_id = {user_id}")

    service = get_google_service()
    sheet = service.spreadsheets()
    spreadsheet_id = os.getenv("SHEET_ID")
    expire_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")

    try:
        res = sheet.values().get(
            spreadsheetId=spreadsheet_id,
            range="PRO!A2:D1000"
        ).execute()
        rows = res.get("values", [])
        print(f"Знайдено {len(rows)} рядків у PRO")
    except Exception as e:
        print("❌ Не вдалося отримати записи з Google Sheets:", e)
        await message.reply(f"❌ Помилка читання таблиці: {e}")
        return

    matched_rows = [(i + 2, row) for i, row in enumerate(rows) if len(row) >= 1 and row[0] == user_id]
    print(f"matched_rows: {matched_rows}")

    if matched_rows:
        for idx, (row_number, row) in enumerate(matched_rows):
            print(f"➡️ Оновлюємо рядок {row_number} (idx={idx})")
            if idx == 0:
                username = row[1] if len(row) > 1 else ""
                try:
                    sheet.values().update(
                        spreadsheetId=spreadsheet_id,
                        range=f"PRO!A{row_number}:D{row_number}",
                        valueInputOption="USER_ENTERED",
                        body={"values": [[user_id, username, "Активно", expire_date]]}
                    ).execute()
                    print(f"✅ Основний рядок оновлено ({row_number})")
                except Exception as e:
                    print("❌ Не вдалося оновити основний рядок:", e)
            else:
                try:
                    sheet.values().update(
                        spreadsheetId=spreadsheet_id,
                        range=f"PRO!A{row_number}:D{row_number}",
                        valueInputOption="RAW",
                        body={"values": [["", "", "", ""]]}
                    ).execute()
                    print(f"🗑️ Дубль рядок очищено ({row_number})")
                except Exception as e:
                    print("❌ Не вдалося очистити дубль:", e)
    else:
        print("⚠️ Не знайдено такого user_id, додаємо новий")
        try:
            sheet.values().append(
                spreadsheetId=spreadsheet_id,
                range="PRO!A2:D2",
                valueInputOption="USER_ENTERED",
                body={"values": [[user_id, "", "Активно", expire_date]]}
            ).execute()
            print("✅ Додано новий рядок")
        except Exception as e:
            print("❌ Не вдалося додати новий рядок:", e)

    await message.reply(f"✅ PRO активовано для {user_id} до {expire_date}")

    try:
        await bot.send_message(
            chat_id=int(user_id),
            text=f"🎉 Ваш PRO доступ активовано до {expire_date}! Дякуємо за підтримку 💛"
        )
        print(f"✅ Сповіщення надіслано користувачу {user_id}")
    except Exception as e:
        print(f"⚠️ Не вдалося надіслати повідомлення користувачу {user_id}: {e}")

from google_api import find_film_by_name

from aiogram.filters import Command

# 🚀 Обробник команди /start
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    # 1) Записуємо користувача
    add_user_if_not_exists(
        user_id=message.from_user.id,
        username=message.from_user.username or "",
        first_name=message.from_user.first_name or ""
    )

    # 2) Дістаємо payload після /start
    payload = None
    if message.text and len(message.text.split()) > 1:
        payload = message.text.split(maxsplit=1)[1].strip()

    # 🧩 Перевірка реферального запрошення
    if payload and payload.startswith("ref_"):
        inviter_id = payload.replace("ref_", "")
        if str(inviter_id) != str(message.from_user.id):
            update_referrals(inviter_id, str(message.from_user.id))
            print(f"🎯 Користувач {message.from_user.id} прийшов за реф-посиланням від {inviter_id}")

    # 3) Якщо payload відсутній — просто показуємо кнопку WebApp
    if not payload or not (payload.startswith("film_") or payload.startswith("series_")):
        await safe_send(
            bot,
            message.chat.id,
            "☕ Хочеш трохи відпочити? Натискай кнопку — усе вже готово!",
            reply_markup=webapp_keyboard
        )
        return

    # 4) Якщо payload валідний — дістаємо id і шукаємо фільм
    film_id = payload.split("_", 1)[1]
    films = get_gsheet_data()

    found = next(
        (f for f in films
         if str(f.get("message_id", "")).strip() == film_id
         or str(f.get("file_id", "")).strip() == film_id),
        None
    )

    if not found:
        await safe_send(
            bot,
            message.chat.id,
            "🎬 Відкрий застосунок і обери фільм 👇",
            reply_markup=webapp_keyboard
        )
        return

    name = found.get("Назва", "Без назви")
    desc = found.get("Опис", "Без опису")
    msg_id = found.get("message_id")
    file_id = found.get("file_id")
    channel_id = int(found.get("channel_id") or os.getenv("MEDIA_CHANNEL_ID"))

    caption = (
        f"*🎬 {name}*\n{desc}\n\n"
        "🎞️🤩 Попкорн є? Світло вимкнено?\n"
        "🚀 Бо цей фільм точно не дасть засумувати!"
    )

    try:
        if msg_id:
            await bot.copy_message(
                chat_id=message.chat.id,
                from_chat_id=channel_id,
                message_id=int(msg_id),
                caption=caption,
                parse_mode="Markdown"
            )
        elif file_id:
            await bot.send_video(
                chat_id=message.chat.id,
                video=file_id,
                caption=caption,
                parse_mode="Markdown"
            )

        # 🧩 Після надсилання — отримуємо file_id (якщо його ще нема)
        if not file_id and msg_id:
            await asyncio.sleep(1.5)  # коротка пауза перед запитом
            file_id = await get_file_id_from_message(bot, channel_id, int(msg_id))
            if file_id:
                print(f"✅ Отримано file_id: {file_id}")
                ok = sb_update_fileid_by_message_id(msg_id, file_id)
                if ok:
                    print(f"💾 file_id записано у Supabase для message_id={msg_id}")
                    sb_update_telegram_url_by_file_id(file_id)
                else:
                    print(f"⚠️ Не вдалося записати file_id у Supabase (message_id={msg_id})")
            else:
                print(f"⚠️ Не вдалося отримати file_id для message_id={msg_id}")

        # 🧰 Telegram CDN "kick fix" — змушує Telegram швидше підʼєднати відео
        await asyncio.sleep(1)
        await bot.send_chat_action(chat_id=message.chat.id, action="upload_video")
        print("⚙️ CDN refresh triggered for better playback")

    except Exception as e:
        print(f"❌ Помилка копіювання відео: {e}")
        await safe_send(bot, message.chat.id, "⚠️ Не вдалося відправити відео")




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
        return

    # --- Пошук фільму
    if not message.text:
        return

    query = message.text.strip()
    films = get_gsheet_data()
    found = find_film_by_name(query)  # твоя функція знаходить фільм за назвою

    if not found:
        await safe_send(bot, message.chat.id, "Фільм не знайдено 😢")
        return

    name = found.get("Назва", "Без назви")
    desc = found.get("Опис", "Без опису")
    msg_id = found.get("message_id")
    file_id = found.get("file_id")
    channel_id = int(found.get("channel_id") or os.getenv("MEDIA_CHANNEL_ID"))

    caption = (
        f"*🎬 {name}*\n{desc}\n\n"
        "🎞️🤩 Попкорн є? Світло вимкнено?\n"
        "🚀 Бо цей фільм точно не дасть засумувати!"
    )

    print(f"✅ Надсилаємо фільм: {name}")
    print(f"🆔 message_id: {msg_id} | file_id: {file_id} | channel: {channel_id}")

    try:
        if msg_id:
            await bot.copy_message(
                chat_id=message.chat.id,
                from_chat_id=channel_id,
                message_id=int(msg_id),
                caption=caption,
                parse_mode="Markdown"
            )
        elif file_id:
            await bot.send_video(
                chat_id=message.chat.id,
                video=file_id,
                caption=caption,
                parse_mode="Markdown"
            )
        else:
            await message.answer(caption, parse_mode="Markdown")

        # 🧩 Після надсилання — отримуємо file_id (якщо його ще нема)
        if not file_id and msg_id:
            await asyncio.sleep(1.5)  # коротка пауза перед запитом
            file_id = await get_file_id_from_message(bot, channel_id, int(msg_id))
            if file_id:
                print(f"✅ Отримано file_id: {file_id}")
                ok = sb_update_fileid_by_message_id(msg_id, file_id)
                if ok:
                    print(f"💾 file_id записано у Supabase для message_id={msg_id}")
                    sb_update_telegram_url_by_file_id(file_id)
                else:
                    print(f"⚠️ Не вдалося записати file_id у Supabase (message_id={msg_id})")
            else:
                print(f"⚠️ Не вдалося отримати file_id для message_id={msg_id}")

        # 🧰 Telegram CDN "kick fix"
        await asyncio.sleep(1)
        await bot.send_chat_action(chat_id=message.chat.id, action="upload_video")
        print("⚙️ CDN refresh triggered for better playback")

    except Exception as e:
        print(f"❌ Помилка копіювання відео: {e}")
        await safe_send(bot, message.chat.id, "⚠️ Не вдалося відправити відео")


    
