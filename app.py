from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.responses import RedirectResponse
from aiogram import types
from bot import dp, bot
from google_api import get_gsheet_data, get_google_service
import os
import requests
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
import asyncio
from datetime import datetime, timedelta
import json
from pytz import timezone
from google_api import add_user_if_not_exists
from pydantic import BaseModel
from typing import Optional
from fastapi import Body
from pro_utils import has_active_pro
import logging
import sys
from json_log_formatter import JSONFormatter
from bot import safe_send_admin
import dateutil.parser
from fastapi import Request
from utils.date_utils import safe_parse_date
from contextlib import asynccontextmanager
from supabase_api import get_films
import random
from fastapi.responses import HTMLResponse

# 🎬 Варіанти фінальних фраз під описом фільму
FUN_CAPTIONS = [
    "🎞️🤩 Попкорн є? Світло вимкнено?\n🚀 Цей фільм точно не дасть засумувати!",
    "🍿 Готовий до кіношного кайфу?\n🎬 Тисни Play і забувай про все!",
    "🌙 Ідеальний момент для фільму.\n🔥 Лови атмосферу вечора!",
    "🎥 Постав чай, вдягни плед — кіно починається ❤️",
    "🤩 Без спойлерів, але фінал тебе здивує 😉",
    "💥 Увімкни фільм і насолоджуйся якістю!",
    "🎬 Це той випадок, коли фільм кращий за серіал 😎",
]

# singleton Google Sheets client
from google_api import get_google_service
SERVICE = get_google_service()
SHEETS = SERVICE.spreadsheets()

# 🧹 Авто-видалення дубльованих постів у дзеркальному каналі
async def schedule_message_delete(bot, chat_id: int, message_id: int, delay_hours: int = 6, user_id: int = None):
    """
    Видаляє повідомлення з каналу (і користувача, якщо задано) через delay_hours.
    Також очищає запис у таблиці 'Видалення'.
    """
    try:
        # ⏳ Конвертуємо години у секунди
        delay_seconds = delay_hours * 3600
        await asyncio.sleep(delay_seconds)

        # 🗑️ Видаляємо повідомлення
        try:
            await bot.delete_message(chat_id=chat_id, message_id=message_id)
            print(f"🗑️ Повідомлення {message_id} видалено з {chat_id}")
        except Exception as e:
            print(f"⚠️ Не вдалося видалити повідомлення {message_id}: {e}")

        # 🚫 Видаляємо користувача з каналу, якщо задано
        if user_id:
            try:
                await bot.ban_chat_member(chat_id=chat_id, user_id=user_id)
                await bot.unban_chat_member(chat_id=chat_id, user_id=user_id)
                print(f"🚫 Користувача {user_id} видалено з каналу {chat_id}")
            except Exception as e:
                print(f"⚠️ Не вдалося видалити користувача {user_id} з каналу {chat_id}: {e}")

        # 🧹 Очищаємо запис про відправлення з таблиці "Видалення"
        try:
            sheet = get_google_service().spreadsheets()
            rows = sheet.values().get(
                spreadsheetId=os.getenv("SHEET_ID"),
                range="Видалення!A2:C1000"
            ).execute().get("values", [])

            for idx, row in enumerate(rows, start=2):
                if len(row) < 2:
                    continue
                if row[0] == str(chat_id) and row[1] == str(message_id):
                    sheet.values().update(
                        spreadsheetId=os.getenv("SHEET_ID"),
                        range=f"Видалення!A{idx}:C{idx}",
                        valueInputOption="RAW",
                        body={"values": [["", "", ""]]}
                    ).execute()
                    print(f"🧹 Видалено рядок з таблиці 'Видалення' ({chat_id}, {message_id})")
                    break
        except Exception as e:
            print(f"⚠️ Не вдалося очистити таблицю 'Видалення': {e}")

    except Exception as e:
        print(f"⚠️ Помилка у schedule_message_delete: {e}")



# ==== Supabase REST helper ====
SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_ANON_KEY = (
    os.getenv("SUPABASE_ANON_KEY")
    or os.getenv("SUPABASE_ANON")
    or ""
)

def _sb_headers():
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        raise RuntimeError("Supabase URL/KEY не задані в ENV")
    return {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
    }


def sb_find_by_name_like(name: str):
    # Пошук за частковою назвою
    import urllib.parse
    q = urllib.parse.quote(f"*{name}*")
    url = f"{SUPABASE_URL}/rest/v1/films?select=*&title=ilike.{q}&limit=50"
    r = requests.get(url, headers=_sb_headers(), timeout=10)
    r.raise_for_status()
    return r.json()

def sb_find_by_message_id(mid: str):
    import urllib.parse
    mid = urllib.parse.quote(mid)
    url = f"{SUPABASE_URL}/rest/v1/films?select=*&message_id=eq.{mid}&limit=1"
    r = requests.get(url, headers=_sb_headers(), timeout=10)
    r.raise_for_status()
    return r.json()

def sb_find_by_file_id(fid: str):
    import urllib.parse
    fid = urllib.parse.quote(fid)
    url = f"{SUPABASE_URL}/rest/v1/films?select=*&file_id=eq.{fid}&limit=1"
    r = requests.get(url, headers=_sb_headers(), timeout=10)
    r.raise_for_status()
    return r.json()

def sb_find_by_message_and_channel(mid: str, ch: str):
    import urllib.parse
    mid_q = urllib.parse.quote(str(mid))
    ch_q  = urllib.parse.quote(str(ch))
    url = f"{SUPABASE_URL}/rest/v1/films?select=*&message_id=eq.{mid_q}&channel_id=eq.{ch_q}&limit=1"
    r = requests.get(url, headers=_sb_headers(), timeout=10)
    r.raise_for_status()
    return r.json()

def sb_find_by_file_and_channel(fid: str, ch: str):
    import urllib.parse
    fid_q = urllib.parse.quote(str(fid))
    ch_q  = urllib.parse.quote(str(ch))
    url = f"{SUPABASE_URL}/rest/v1/films?select=*&file_id=eq.{fid_q}&channel_id=eq.{ch_q}&limit=1"
    r = requests.get(url, headers=_sb_headers(), timeout=10)
    r.raise_for_status()
    return r.json()

async def clean_old_requests_once():
    """Одноразово видаляє записи старше 31 дня з аркуша 'Замовлення'."""
    from pytz import timezone
    from datetime import datetime, timedelta

    kyiv = timezone("Europe/Kyiv")
    sheet = SHEETS

    # 1) Забираємо всі рядки
    rows = sheet.values().get(
        spreadsheetId=os.getenv("SHEET_ID"),
        range="Замовлення!A2:C1000"
    ).execute().get("values", [])

    now = datetime.now(kyiv)
    to_clear = []

    for idx, row in enumerate(rows, start=2):
        if len(row) < 3:
            continue
        ts_str = row[2]
        try:
            ts = kyiv.localize(datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S"))
        except:
            continue
        # якщо старше 31 дня
        if now - ts > timedelta(days=31):
            to_clear.append(idx)

    # 2) Очищаємо знайдені рядки
    for row_num in to_clear:
        sheet.values().update(
            spreadsheetId=os.getenv("SHEET_ID"),
            range=f"Замовлення!A{row_num}:C{row_num}",
            valueInputOption="RAW",
            body={"values": [["", "", ""]]}
        ).execute()


# —————— JSON-логер ——————
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JSONFormatter())

access_logger = logging.getLogger("uvicorn.access")
access_logger.setLevel(logging.INFO)
access_logger.addHandler(handler)

error_logger = logging.getLogger("uvicorn.error")
error_logger.setLevel(logging.INFO)
error_logger.addHandler(handler)
# ————————————————



class RateRequest(BaseModel):
    film_name: str
    action: str            # наприклад, "like" або "dislike"
    undo: Optional[str] = None  # опціональне, "like" або "dislike" або None

class SearchRequest(BaseModel):
    user_id: int
    query: str
    username: Optional[str] = None
    first_name: Optional[str] = None

class AdminMessage(BaseModel):
    user_id: int
    text: str



# Список повідомлень, які потрібно буде видалити
messages_to_delete = []


from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 🚫 НЕ ставимо webhook при старті, щоб не падало
    from bot import clean_expired_pro
    await asyncio.to_thread(clean_expired_pro)
    yield


    

# ✅ Оголошення FastAPI ДО використання декораторів
app = FastAPI(lifespan=lifespan)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # ← дозволяємо всі Origin для дебагу
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.get("/set-webhook")
async def set_webhook():
    webhook_url = os.getenv("WEBHOOK_URL")
    if not webhook_url:
        return {"error": "WEBHOOK_URL не задано"}
    try:
        await bot.set_webhook(webhook_url)
        return {"status": "ok", "url": webhook_url}
    except Exception as e:
        return {"error": str(e)}


BAD_BOTS = [
    "Googlebot", "Bingbot", "AhrefsBot", "YandexBot", "SEMRushBot",
    "DotBot", "MJ12bot", "facebookexternalhit", "Applebot", "DuckDuckBot"
]

@app.middleware("http")
async def block_bots(request: Request, call_next):
    user_agent = request.headers.get("User-Agent", "")
    if any(bot.lower() in user_agent.lower() for bot in BAD_BOTS):
        raise HTTPException(status_code=403, detail="Bots are not allowed")
    return await call_next(request)


# ✅ ДОДАЙ ОЦЕ СЮДИ
@app.get("/")
async def root():
    return {"status": "alive"}
    
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

@app.get("/watch/{film_id}")
async def watch_film(film_id: str, request: Request):
    """
    Дублює фільм або серію у відповідний дзеркальний канал.
    Для публічних каналів invite-link не створюється — генерується пряме посилання.
    """
    try:
        import urllib.parse, requests, os, asyncio
        from datetime import datetime, timedelta
        from fastapi.responses import RedirectResponse, HTMLResponse
        from bot import bot  # ✅ імпорт тільки бота

        SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
        SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_ANON") or ""
        headers = {"apikey": SUPABASE_ANON_KEY, "Authorization": f"Bearer {SUPABASE_ANON_KEY}"}

        # 🔍 Отримуємо запис із таблиці
        film_id_q = urllib.parse.quote(str(film_id))
        url = f"{SUPABASE_URL}/rest/v1/films?select=*&id=eq.{film_id_q}&limit=1"
        r = requests.get(url, headers=headers, timeout=10)
        data = r.json()
        if not data:
            print(f"⚠️ Не знайдено запис із ID {film_id}")
            return {"error": "Фільм або серіал не знайдено"}

        film = data[0]
        # 👤 user_id передається з WebApp через ?user_id=
        try:
            user_id = int(request.query_params.get("user_id", 0))
        except:
            user_id = int(film.get("user_id") or 0)

        print(f"👤 USER_ID = {user_id}")
        source_channel = int(film.get("channel_id") or os.getenv("MEDIA_CHANNEL_ID"))
        message_id = int(film.get("message_id"))
        film_type = (film.get("type") or "").strip().lower()
        title = film.get("title") or film.get("Назва") or "Без назви"
        access = (film.get("access") or film.get("Доступ") or "").upper()

        print(f"🧾 ID={film_id} | type='{film_type}' | title='{title}' | message_id={message_id}")

        # 🪞 Вибір дзеркального каналу
        if access == "PRO":
            if any(x in film_type for x in ["серіал", "серія"]):
                mirror_channel = int(os.getenv("MEDIA_CHANNEL_MIRROR_PRO_SERIES", "-1003004556512"))
                channel_label = "👑 PRO Серіал → RelaxBox PRO | Серіали"
                delay_hours = 3
            else:
                mirror_channel = int(os.getenv("MEDIA_CHANNEL_MIRROR_PRO_FILMS", "-1003160463240"))
                channel_label = "👑 PRO Фільм → RelaxTime PRO | Фільми"
                delay_hours = 6
        elif any(x in film_type for x in ["серіал", "серія"]):
            mirror_channel = int(os.getenv("MEDIA_CHANNEL_MIRROR_SERIES", "-1003153440872"))
            channel_label = "📺 Серіал → RelaxBox | Серіали"
            delay_hours = 3
        else:
            mirror_channel = int(os.getenv("MEDIA_CHANNEL_MIRROR_FILMS", "-1002863248325"))
            channel_label = "🎬 Фільм → RelaxTime View"
            delay_hours = 6

        print(f"➡️ Тип: {film_type} | Дзеркало: {mirror_channel} ({channel_label})")

        # 📝 Формуємо опис
        description = (film.get("description") or film.get("Опис") or "").strip()
        extra_phrase = random.choice(FUN_CAPTIONS)
        invite_text = "\n\n🚨 <b>УВАГА!</b> 🔴\n👉 <b>ПІДПИСАТИСЯ НА КАНАЛ 🔔</b>"
        final_caption = f"🎬 {title}\n\n{description}\n\n{extra_phrase}{invite_text}"

                # 🎬 Копіюємо відео в дзеркальний канал
        # Але спершу перевіримо, чи message_id коректний (щоб не було Telegram error)
        if not str(message_id).isdigit():
            html = """
            <html>
            <head>
                <meta charset="utf-8">
                <title>🎞 Фільм недоступний</title>
                <style>
                    body {
                        background: #0f0f0f;
                        color: #fff;
                        font-family: 'Russo One', sans-serif;
                        display: flex;
                        flex-direction: column;
                        align-items: center;
                        justify-content: center;
                        height: 100vh;
                        text-align: center;
                    }
                    h1 { font-size: 30px; margin-bottom: 15px; color: #00f7ff; }
                    p { font-size: 17px; color: #ccc; max-width: 340px; line-height: 1.5; }
                    a {
                        display: inline-block;
                        margin-top: 25px;
                        padding: 10px 22px;
                        background: linear-gradient(90deg, #00f7ff, #ff00d4);
                        color: #000;
                        border-radius: 10px;
                        text-decoration: none;
                        font-weight: bold;
                    }
                </style>
            </head>
            <body>
                <h1>🎬 Фільм недоступний</h1>
                <p>На жаль, це відео не може бути відтворене 😔<br>
                Спробуйте інший фільм або поверніться пізніше 💫</p>
                <a href="https://relaxbox.site/">🔁 Повернутись до каталогу</a>
            </body>
            </html>
            """
            return HTMLResponse(content=html, status_code=200)

        # якщо все добре — копіюємо відео
        mirror_msg = await bot.copy_message(
            chat_id=mirror_channel,
            from_chat_id=source_channel,
            message_id=message_id,
            caption=final_caption,
            parse_mode="HTML"
        )

        print(f"✅ {title} дубльовано → {channel_label}")

        # 🔗 Формуємо пряме посилання
        public_id = str(mirror_channel).replace("-100", "")
        tg_url = f"https://t.me/c/{public_id}/{mirror_msg.message_id}"
        print(f"🌍 Згенеровано публічне посилання: {tg_url}")

        # 🕓 Авто-видалення з каналу
        asyncio.create_task(schedule_message_delete(bot, mirror_channel, mirror_msg.message_id, delay_hours, user_id))

        # 🧾 Запис у таблицю
        kyiv = timezone("Europe/Kyiv")
        delete_time = datetime.now(kyiv) + timedelta(hours=delay_hours)
        sheet = get_google_service().spreadsheets()
        sheet.values().append(
            spreadsheetId=os.getenv("SHEET_ID"),
            range="Видалення!A2",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values": [[str(mirror_channel), str(mirror_msg.message_id), delete_time.isoformat()]]}
        ).execute()

        # 📩 Надсилаємо користувачу коротке повідомлення з кнопкою
        if user_id:
            try:
                from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

                keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="▶️ Дивитись фільм", url=tg_url)]
                    ]
                )
                msg = await bot.send_message(
                    chat_id=int(user_id),
                    text=f"🎬 <b>{title}</b>",
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
                asyncio.create_task(schedule_message_delete(bot, int(user_id), msg.message_id, delay_hours))
                print(f"📨 Повідомлення користувачу {user_id} надіслано з кнопкою й заплановано на видалення")
            except Exception as e:
                print(f"⚠️ Не вдалося надіслати повідомлення користувачу {user_id}: {e}")

        # 🔁 Перенаправлення у Telegram
        return RedirectResponse(url=tg_url)


    except Exception as e:
        print(f"❌ Помилка у /watch/{film_id}: {e}")
        # Якщо це повідомлення не знайдено — показуємо спокійний текст у WebApp
        if "message to copy not found" in str(e) or "wrong remote file identifier" in str(e).lower():
            html = """
            <html>
            <head>
                <meta charset="utf-8">
                <title>🎞 Фільм недоступний</title>
                <style>
                    body {
                    background: #0f0f0f;
                    color: #fff;
                    font-family: 'Russo One', sans-serif;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    height: 100vh;
                    text-align: center;
                }
                h1 {
                    font-size: 30px;
                    margin-bottom: 15px;
                    color: #00f7ff;
                }
                p {
                    font-size: 17px;
                    color: #ccc;
                    max-width: 340px;
                    line-height: 1.5;
                }
                a {
                    display: inline-block;
                    margin-top: 25px;
                    padding: 10px 22px;
                    background: linear-gradient(90deg, #00f7ff, #ff00d4);
                    color: #000;
                    border-radius: 10px;
                    text-decoration: none;
                    font-weight: bold;
                }
            </style>
        </head>
        <body>
            <h1>🎬 Фільм тимчасово недоступний</h1>
            <p>На жаль, це відео зараз недоступне або було видалене 😔<br>
            Спробуйте обрати інший фільм або зайдіть пізніше 💫</p>
            <a href="https://relaxbox.site/">🔁 Повернутись до каталогу</a>
        </body>
        </html>
        """
            return HTMLResponse(content=html, status_code=200)

        # Якщо інша помилка — теж відобразимо красиво
        html = f"""
        <html>
        <head><meta charset="utf-8"><title>Помилка</title></head>
        <body style="background:#111;color:#fff;font-family:sans-serif;text-align:center;padding-top:100px;">
            <h2>⚠️ Помилка</h2>
            <p>{str(e)}</p>
        </body>
        </html>
        """
        return HTMLResponse(content=html, status_code=200)



@app.post("/notify-payment")
async def notify_payment(req: Request):
    data = await req.json()
    user_id = data.get("user_id")
    username = data.get("username", "")
    first_name = data.get("first_name", "")

    if not user_id:
        raise HTTPException(status_code=400, detail="user_id відсутній")

    service = get_google_service()
    sheet = service.spreadsheets()

    kyiv = timezone("Europe/Kyiv")
    now_kyiv = datetime.now(kyiv).strftime("%Y-%m-%d %H:%M:%S")

    sheet.values().append(
        spreadsheetId=os.getenv("SHEET_ID"),
        range="PRO!A2:D2",
        valueInputOption="USER_ENTERED",
        body={"values": [[str(user_id), username, "Очікує підтвердження", now_kyiv]]}
    ).execute()
    
    admin_id = os.getenv("ADMIN_ID")
    await safe_send_admin(
        bot, admin_id,
        f"💳 Користувач [{first_name}](tg://user?id={user_id}) натиснув 'Я оплатив'\n\n✅ Щоб підтвердити PRO, надішли:\n`/ok {user_id}`",
        parse_mode="Markdown"
    )

    return {"ok": True}

from uuid import uuid4

@app.post("/create-payment")
async def create_payment(req: Request):
    data = await req.json()
    user_id = data.get("user_id")
    username = data.get("username", "")
    first_name = data.get("first_name", "")
    plan = data.get("plan", "pro30")

    if not user_id:
        raise HTTPException(status_code=400, detail="user_id відсутній")

    invoice_id = str(uuid4())  # генеруємо унікальний ID заявки
    kyiv = timezone("Europe/Kyiv")
    now_kyiv = datetime.now(kyiv).strftime("%Y-%m-%d %H:%M:%S")

    # 🔹 Записуємо у Google Таблицю (для історії)
    sheet = get_google_service().spreadsheets()
    sheet.values().append(
        spreadsheetId=os.getenv("SHEET_ID"),
        range="PRO!A2:E2",
        valueInputOption="USER_ENTERED",
        body={"values": [[str(user_id), username, f"Створив оплату ({plan})", now_kyiv, invoice_id]]}
    ).execute()

    # 🔹 Повідомляємо адміну
    admin_id = os.getenv("ADMIN_ID")
    await safe_send_admin(
        bot, admin_id,
        f"🟢 Користувач [{first_name}](tg://user?id={user_id}) натиснув 'Отримати PRO'\n"
        f"📌 План: {plan}\n🆔 invoice: {invoice_id}",
        parse_mode="Markdown"
    )

    return {"ok": True, "invoice_id": invoice_id}

@app.post('/contact-admin')
async def contact_admin(msg: AdminMessage):
    admin_id = int(os.getenv("ADMIN_ID", "7963871119"))
    reply_cmd = f"/reply {msg.user_id} "
    text = (
        f"✉️ Нове повідомлення від користувача {msg.user_id}:\n\n"
        f"{msg.text}\n\n"
        f"Для відповіді: <code>{reply_cmd}ваш_текст</code>"
    )

    # Додаємо кнопку для копіювання /reply
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Скопіювати команду", switch_inline_query=reply_cmd)]
        ]
    )
    await safe_send_admin(bot, admin_id, text, parse_mode="HTML", reply_markup=keyboard)
    return {'ok': True}



@app.post("/request-film")
async def request_film(req: Request):
    try:
        data = await req.json()
        user_id = str(data.get('user_id'))
        film_name = data.get('film_name')

        if not user_id or not film_name:
            return JSONResponse(status_code=400, content={"success": False, "error": "user_id або film_name відсутні"})

        is_pro = has_active_pro(user_id)
        remaining = None

        # 🔒 Якщо користувач не має PRO — перевіряємо ліміт
        if not is_pro:
            service = get_google_service()
            sheet = service.spreadsheets()

            kyiv = timezone("Europe/Kyiv")
            now = datetime.now(kyiv)
            one_month_ago = now - timedelta(days=30)

            result = sheet.values().get(
                spreadsheetId=os.getenv("SHEET_ID"),
                range="Замовлення!A2:C1000"
            ).execute().get("values", [])

            user_requests = []
            for row in result:
                if len(row) < 3 or row[0] != user_id:
                    continue
                try:
                    row_time = timezone("Europe/Kyiv").localize(datetime.strptime(row[2], "%Y-%m-%d %H:%M:%S"))
                    if row_time >= one_month_ago:
                        user_requests.append(row)
                except Exception as e:
                    print(f"⚠️ Помилка розбору дати: {e}")
                    continue

            max_free_requests = 5
            remaining = max_free_requests - len(user_requests)

            if remaining <= 0:
                print(f"⛔ {user_id} перевищив ліміт. Запитів: {len(user_requests)}")
                return JSONResponse(status_code=403, content={
                    "success": False,
                    "error": (
                        "⛔ Ви вже використали всі 5 безкоштовних запитів цього місяця.\n\n"
                        "🚀 Отримайте PRO — і замовляйте скільки завгодно!"
                    ),
                    "remaining_requests": 0,
                    "is_pro": is_pro
                })
            else:
                print(f"✅ У користувача {user_id} ще {remaining} безкоштовних запитів")

        # ✅ Записуємо замовлення
        service = get_google_service()
        sheet = service.spreadsheets()
        now_str = datetime.now(timezone("Europe/Kyiv")).strftime("%Y-%m-%d %H:%M:%S")

        sheet.values().append(
            spreadsheetId=os.getenv("SHEET_ID"),
            range="Замовлення!A2:C2",
            valueInputOption="USER_ENTERED",
            body={"values": [[user_id, film_name, now_str]]}
        ).execute()

        # 📨 Надсилаємо повідомлення адміну
        message = f"🎬 Користувач {user_id} хоче додати фільм: {film_name}"
        await safe_send_admin(
            bot, int(os.getenv("ADMIN_ID", "7963871119")), message, parse_mode=None
        )
        
        return {
            "success": True,
            "remaining_requests": remaining if remaining is not None else "∞",
            "is_pro": is_pro
        }

    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    update = types.Update(**data)
    await dp.feed_update(bot, update)
    return {"ok": True}

from bot import bot
from fastapi.responses import JSONResponse

@app.post("/search-in-bot")
async def search_in_bot(data: SearchRequest):
    user_id = data.user_id
    query   = data.query.lower().strip()
    username  = data.username or ""
    first_name = data.first_name or ""

    if user_id:
        add_user_if_not_exists(user_id, username, first_name)

    if not user_id or not query:
        return {"found": False}

    # знаходимо рядок, де є message_id
    rows = sb_find_by_name_like(query)
    found = next((f for f in rows if f.get("message_id")), None)

    if not found:
        return {"found": False}

    # копіюємо це відео з вашого каналу-репозиторію в чат користувача
    try:
        await bot.copy_message(
            chat_id=int(user_id),
            from_chat_id=int(found.get("channel_id") or os.getenv("MEDIA_CHANNEL_ID")),
            message_id=int(found["message_id"]),
        )
    except Exception as e:
        # якщо щось пішло не так — повертаємо помилку
        return JSONResponse(status_code=500, content={"found": True, "error": str(e)})

    # повертаємо фронтенду лише прапорець успіху
    return {"found": True, "sent": True}

from fastapi.responses import JSONResponse

@app.post("/send-film")
async def send_film(request: Request):
    try:
        data = await request.json()
        user_id = data.get("user_id")
        film_name = data.get("film_name")

        username = data.get("username", "")
        first_name = data.get("first_name", "")

        if user_id:
            add_user_if_not_exists(user_id, username, first_name)



        if not user_id or not film_name:
            return JSONResponse(status_code=400, content={"success": False, "error": "user_id або film_name відсутні"})

        rows = sb_find_by_name_like(film_name)
        found_film = next((f for f in rows if f.get("message_id")), None)

        if not found_film:
            return JSONResponse(status_code=404, content={"success": False, "error": "Фільм не знайдено або немає file_id"})

        # 🔒 Перевірка доступу PRO
        if found_film.get("access") == "PRO" and not has_active_pro(str(user_id)):
            return JSONResponse(
                status_code=403,
                content={"success": False, "error": "⛔ Доступ лише для PRO користувачів"}
                )


        # Готуємо клавіатуру
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(
                    text="🎥 Обрати інший фільм 📚",
                    web_app=WebAppInfo(url="https://relaxbox.site/")
                )]
            ]
        )

        # Час видалення
        kyiv = timezone("Europe/Kyiv")
        delete_time = datetime.now(kyiv) + timedelta(hours=24)
        delete_time_str = delete_time.strftime('%H:%M %d.%m')

        caption = (
            "🎬 Приємного перегляду! 🍿\n\n"
            f"🕓 Це повідомлення буде видалено о {delete_time_str} (за Києвом)."
        )

        message_id = int(found_film.get("message_id") or found_film.get("file_id"))
        channel_id = int(found_film.get("channel_id") or os.getenv("MEDIA_CHANNEL_ID"))

        if found_film.get("file_id"):
            print(f"🎬 Відправка через file_id={found_film['file_id']} → {found_film.get('title')}")
            sent_message = await bot.send_video(
                chat_id=int(user_id),
                video=found_film["file_id"],
                caption=caption,
                reply_markup=keyboard,
                parse_mode="HTML",
                supports_streaming=True
            )
        else:
            print(f"📦 Відправка копією (message_id={message_id}) → {found_film.get('title')}")
            sent_message = await bot.copy_message(
                chat_id=int(user_id),
                from_chat_id=channel_id,
                message_id=message_id
            )
        try:
            await bot.edit_message_caption(
                chat_id=int(user_id),
                message_id=sent_message.message_id,
                caption=caption,
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
        except Exception as e:
            if "message is not modified" not in str(e):
                print(f"⚠️ Не вдалося оновити caption: {e}")

        # Зберігаємо для видалення
        service = get_google_service()
        sheet = service.spreadsheets()
        sheet.values().append(
            spreadsheetId=os.getenv("SHEET_ID"),
            range="Видалення!A2",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values": [[str(user_id), str(sent_message.message_id), delete_time.isoformat()]]}
            ).execute()

        print(f"✅ Відео надіслано користувачу {user_id}")

        return {"success": True}

    except Exception as e:
        print(f"❌ Помилка в /send-film: {e}")
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

@app.post("/send-film-id")
async def send_film_by_id(request: Request):
    """
    Дублює фільм або серію у дзеркальний канал і повертає посилання.
    ⚙️ Працює лише через message_id (без file_id).
    """
    try:
        data = await request.json()
        user_id = str(data.get("user_id"))
        message_id = str(data.get("message_id", "")).strip()
        channel_in = str(data.get("channel_id", "")).strip()

        if not user_id or user_id == "0":
            print("❌ USER_ID порожній або 0 — не відправляємо фільм")
            return {"success": False, "error": "Некоректний user_id (0 або порожній)"}

        print(f"📽️ /send-film-id {message_id} від {user_id}")
        print(f"    channel_in={channel_in}")

        # 🔍 Отримуємо фільм або серію із Supabase
        rows = sb_find_by_message_and_channel(message_id, channel_in) if channel_in else sb_find_by_message_id(message_id)
        if not rows:
            return {"success": False, "error": "Фільм не знайдено"}

        row = rows[0]
        title = row.get("title") or row.get("Назва") or "Без назви"
        film_type = (row.get("type") or row.get("Тип") or "").lower()
        access = (row.get("access") or row.get("Доступ") or "").upper()
        source_channel = int(row.get("channel_id") or os.getenv("MEDIA_CHANNEL_ID"))

        # 🪞 Вибираємо дзеркальний канал
        mirror_films = int(os.getenv("MEDIA_CHANNEL_MIRROR_FILMS", "-1002863248325"))
        mirror_series = int(os.getenv("MEDIA_CHANNEL_MIRROR_SERIES", "-1003153440872"))
        mirror_pro_films = int(os.getenv("MEDIA_CHANNEL_MIRROR_PRO_FILMS", "-1003160463240"))
        mirror_pro_series = int(os.getenv("MEDIA_CHANNEL_MIRROR_PRO_SERIES", "-1003004556512"))

        # 🔍 Визначаємо, серіал це чи фільм
        film_type_lower = film_type.lower()
        is_series = any(word in film_type_lower for word in ["серіал", "серія", "season", "episode", "ep", "s0", "e0"])

        if access == "PRO":
            if is_series:
                mirror_channel = mirror_pro_series
                delay_hours = 3
                print(f"👑 PRO серіал {title} → {mirror_channel}")
            else:
                mirror_channel = mirror_pro_films
                delay_hours = 6
                print(f"👑 PRO фільм {title} → {mirror_channel}")
        elif is_series:
            mirror_channel = mirror_series
            delay_hours = 3
            print(f"📺 Серіал {title} → {mirror_channel}")
        else:
            mirror_channel = mirror_films
            delay_hours = 6
            print(f"🎬 Фільм {title} → {mirror_channel}")

        # 📝 Формуємо опис
        description = (row.get("description") or "").strip()
        extra_phrase = random.choice(FUN_CAPTIONS)
        invite_text = "\n\n🚨 <b>УВАГА!</b> 🔴\n👉 <b>ПІДПИСАТИСЯ НА КАНАЛ 🔔</b>"
        caption = f"🎬 {title}\n\n{description}\n\n{extra_phrase}{invite_text}"

        # 🎬 Копіюємо повідомлення у дзеркальний канал
        try:
            mirror_msg = await bot.copy_message(
                chat_id=mirror_channel,
                from_chat_id=source_channel,
                message_id=int(message_id),
                caption=caption,
                parse_mode="HTML"
            )
            print(f"✅ Дубльовано '{title}' у {mirror_channel} (msg_id={mirror_msg.message_id})")
        except Exception as e:
            print(f"❌ Помилка дублювання: {e}")
            return {"success": False, "error": str(e)}

        # 🔗 Генеруємо посилання
        try:
            chat = await bot.get_chat(mirror_channel)
            if chat.username:
                tg_url = f"https://t.me/{chat.username}/{mirror_msg.message_id}"
            else:
                public_id = str(mirror_channel).replace("-100", "")
                tg_url = f"https://t.me/c/{public_id}/{mirror_msg.message_id}"
            print(f"🌍 Згенеровано посилання: {tg_url}")
        except Exception as e:
            print(f"⚠️ Не вдалося отримати username каналу: {e}")
            public_id = str(mirror_channel).replace("-100", "")
            tg_url = f"https://t.me/c/{public_id}/{mirror_msg.message_id}"

        # 🕓 Плануємо авто-видалення
        asyncio.create_task(schedule_message_delete(bot, mirror_channel, mirror_msg.message_id, delay_hours))

        # 🧾 Запис у Google Таблицю “Видалення”
        kyiv = timezone("Europe/Kyiv")
        delete_time = datetime.now(kyiv) + timedelta(hours=delay_hours)
        sheet = get_google_service().spreadsheets()
        sheet.values().append(
            spreadsheetId=os.getenv("SHEET_ID"),
            range="Видалення!A2",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values": [[str(mirror_channel), str(mirror_msg.message_id), delete_time.isoformat()]]}
        ).execute()
        print(f"🧾 Заплановано видалення через {delay_hours} год ({title})")

        # 📩 Надсилаємо користувачу кнопку "Дивитись фільм"
        if user_id:
            try:
                from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

                keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="▶️ Дивитись фільм", url=tg_url)]
                    ]
                )

                msg = await bot.send_message(
                    chat_id=int(user_id),
                    text=f"🎬 <b>{title}</b>",
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )

                asyncio.create_task(schedule_message_delete(bot, int(user_id), msg.message_id, delay_hours))
                print(f"📨 Надіслано кнопку '▶️ Дивитись фільм' користувачу {user_id}")

            except Exception as e:
                print(f"⚠️ Не вдалося надіслати кнопку користувачу {user_id}: {e}")

        return {"success": True, "url": tg_url}

    except Exception as e:
        print(f"⚠️ Помилка у /send-film-id: {e}")
        return {"success": False, "error": str(e)}


@app.post("/check-subscription")
async def check_subscription(request: Request):
    data = await request.json()
    user_id = data.get('user_id')

    if not user_id:
        raise HTTPException(status_code=400, detail="user_id відсутній")

    bot_token = os.getenv("BOT_TOKEN")

    channels = os.getenv("CHANNEL_LIST", "").split(",")  # ← тут заміни на свій другий канал

    subscribed_to_any = False

    for channel_username in channels:
        url = f"https://api.telegram.org/bot{bot_token}/getChatMember"
        params = {
            "chat_id": channel_username,
            "user_id": user_id
        }

        try:
            response = requests.get(url, params=params)
            result = response.json()
            if result.get("ok") and result["result"]["status"] in ["member", "administrator", "creator"]:
                subscribed_to_any = True
                break  # можна припинити перевірку, бо вже є підписка
        except Exception as e:
            print(f"❗️Помилка перевірки підписки на {channel_username}: {e}")

    return {"subscribed": subscribed_to_any}


async def background_deleter():
    service = get_google_service()
    sheet = service.spreadsheets()

    while True:
        from pytz import utc
        now = datetime.now(utc)

        # Отримати всі записи з аркуша "Видалення"
        data = sheet.values().get(
            spreadsheetId=os.getenv("SHEET_ID"),
            range="Видалення!A2:C1000"
        ).execute().get("values", [])

        print(f"🔍 Вміст таблиці Видалення:\n{data}")

        print(f"⏳ Перевірка на видалення: {len(data)} в черзі")

        for i, row in enumerate(data):
            if len(row) < 3:
                continue

            user_id = row[0]
            message_id = row[1]
            delete_at_str = row[2]

            if not user_id.isdigit() or not message_id.isdigit():
                print(f"⚠️ Пропускаємо некоректний рядок: {row}")
                continue

            try:
                delete_at = dateutil.parser.isoparse(delete_at_str)
            except Exception as e:
                print(f"⚠️ Неможливо розпізнати дату: {delete_at_str} — {e}")
                continue

            if now >= delete_at:
                try:
                    await bot.delete_message(chat_id=int(user_id), message_id=int(message_id))
                    print(f"✅ Видалено повідомлення {message_id} у {user_id}")
                except Exception as e:
                    print(f"❌ Помилка видалення повідомлення {message_id}: {e}")

                # Очистити рядок
                row_number = i + 2
                sheet.values().update(
                    spreadsheetId=os.getenv("SHEET_ID"),
                    range=f"Видалення!A{row_number}:C{row_number}",
                    valueInputOption="RAW",
                    body={"values": [["", "", ""]]}
                ).execute()
                    

        
async def background_deleter_once():
    from pytz import utc
    now = datetime.now(utc)
    sheet = SHEETS

    rows = sheet.values().get(
        spreadsheetId=os.getenv("SHEET_ID"),
        range="Видалення!A2:C1000"
    ).execute().get("values", [])

    for idx, row in enumerate(rows, start=2):
        if len(row) < 3:
            continue
        user_id, message_id, delete_at_str = row
        if not (user_id.isdigit() and message_id.isdigit()):
            continue
        try:
            delete_at = dateutil.parser.isoparse(delete_at_str)
        except:
            continue

        if datetime.now(utc) >= delete_at:
            try:
                await bot.delete_message(chat_id=int(user_id), message_id=int(message_id))
            except:
                pass
            sheet.values().update(
                spreadsheetId=os.getenv("SHEET_ID"),
                range=f"Видалення!A{idx}:C{idx}",
                valueInputOption="RAW",
                body={"values":[["","",""]]}
            ).execute()

# … ваш background_deleter_once тут …

async def check_pending_payments_once():
    """
    Одноразово перевіряє PRO!A2:D і обробляє всі записи
    “Очікує підтвердження” старші за 10 хвилин.
    """
    service = get_google_service()
    sheet = service.spreadsheets()
    kyiv = timezone("Europe/Kyiv")
    now = datetime.now(kyiv)

    # 1) Зчитуємо всі рядки
    rows = sheet.values().get(
        spreadsheetId=os.getenv("SHEET_ID"),
        range="PRO!A2:D1000"
    ).execute().get("values", [])
    for idx, row in enumerate(rows, start=2):
        if len(row) < 4:
            continue
        user_id, username, status, created_at_str = row[:4]
        if status != "Очікує підтвердження":
            continue

        # Парсимо дату і порівнюємо
        try:
            created_at = datetime.strptime(created_at_str, "%Y-%m-%d %H:%M:%S")
            # локалізуємо під Київ
            created_at = kyiv.localize(created_at)
        except Exception as e:
            print(f"⚠️ Не вдалося прочитати дату '{created_at_str}': {e}")
            continue

        if now - created_at > timedelta(minutes=10):
            # 2) надсилаємо нагадування
            from bot import safe_send
            await safe_send(
                bot, int(user_id),
                "❗️ Ми не знайшли вашу оплату за PRO-доступ.\n\n"
                "Натисніть «🚀 Повторити оплату» або спробуйте ще раз:",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[[
                        InlineKeyboardButton(
                            text="🚀 Повторити оплату",
                            web_app=WebAppInfo(url="https://relaxbox.site/")
                        )
                    ]]
                )
            )
            print(f"✅ Сповіщено {user_id}, термін очікування минув")

            # 3) Оновлюємо статус у Google Sheets
            print(f"🔧 Готуємо update PRO!A{idx}:C{idx} → ['{user_id}', '{username}', 'Не активовано']")
            sheet.values().update(
                spreadsheetId=os.getenv("SHEET_ID"),
                range=f"PRO!A{idx}:C{idx}",
                valueInputOption="RAW",
                body={"values": [[user_id, username, "Не активовано"]]}
            ).execute()
            print(f"🔧 Статус у PRO!A{idx}:C{idx} змінено на 'Не активовано'")
            print(f"✅ Виконано update PRO!A{idx}:C{idx}")


@app.post("/jobs/check-payments")
async def job_check_payments():
    """
    HTTP-ендпоінт для одноразової перевірки PRO-платежів старших за 10 хв.
    Викликайте через GitHub Actions cron.
    """
    await check_pending_payments_once()
    return {"ok": True, "checked": "pending payments processed"}


async def check_pending_payments():
    service = get_google_service()
    sheet = service.spreadsheets()

    kyiv = timezone("Europe/Kyiv")

    while True:
        print("🔎 Перевірка очікуючих платежів...")  
        now = datetime.now(kyiv).replace(tzinfo=None)  # Часовий пояс Києва
        print(f"🕒 Поточний час: {now}")

        data = sheet.values().get(
            spreadsheetId=os.getenv("SHEET_ID"),
            range="PRO!A2:D1000"
        ).execute().get("values", [])

        print(f"📋 Знайдено записів для перевірки: {len(data)}")

        for i, row in enumerate(data):
            if len(row) < 4:
                continue

            user_id = row[0]
            username = row[1] if len(row) > 1 else ""
            status = row[2]
            created_at_str = row[3]

            if status != "Очікує підтвердження":
                continue

            try:
                created_at = datetime.strptime(created_at_str, "%Y-%m-%d %H:%M:%S")
                print(f"⏰ Запис створений о: {created_at}")
            except Exception as e:
                print(f"⚠️ Помилка формату дати '{created_at_str}': {e}")
                continue

            diff = now - created_at
            print(f"⏳ Пройшло часу: {diff}")

            if diff > timedelta(minutes=10):
                from bot import safe_send

                print(f"⚠️ Термін очікування минув для користувача {user_id}")

                try:
                    await safe_send(
                        bot, int(user_id),
                        "❗️ Ми не знайшли вашу оплату за PRO доступ.\n\n"
                        "Можливо, ви забули оплатити або оплата ще обробляється.\n"
                        "Спробуйте повторити або натисніть кнопку нижче:",
                        reply_markup=InlineKeyboardMarkup(
                            inline_keyboard=[[
                                InlineKeyboardButton(
                                    text="🚀 Повторити оплату",
                                    web_app=WebAppInfo(url="https://relaxbox.site/")
                                )
                            ]]
                        )
                    )
                    print(f"✅ Повідомлення про оплату надіслано користувачу {user_id}")

                except Exception as e:
                    print(f"⚠️ Не вдалося надіслати повідомлення {user_id}: {e}")

                row_number = i + 2
                sheet.values().update(
                    spreadsheetId=os.getenv("SHEET_ID"),
                    range=f"PRO!A{row_number}:C{row_number}",
                    valueInputOption="RAW",
                    body={"values": [[user_id, username, "Не активовано"]]}
                ).execute()

                print(f"🔧 Статус користувача {user_id} змінено на 'Не активовано' у Google Таблиці")

        await asyncio.sleep(60)



from fastapi.responses import JSONResponse

@app.post("/check-pro")
async def check_pro(req: Request):
    data = await req.json()
    user_id = str(data.get("user_id"))
    if not user_id:
        return JSONResponse(status_code=400, content={"error": "user_id відсутній"})

    service = get_google_service()
    sheet = service.spreadsheets()
    res = sheet.values().get(
        spreadsheetId=os.getenv("SHEET_ID"),
        range="PRO!A2:D1000"
    ).execute()
    rows = res.get("values", [])

    kyiv = timezone("Europe/Kyiv")
    today = datetime.now(kyiv).date()

    # Перебираємо з індексом, щоб мати правильний row_number
    for idx, row in enumerate(rows, start=2):
        if len(row) < 4:
            continue
        uid, _, status, exp_str = row[:4]
        if uid.strip() == user_id and status.strip().lower() == "активно":
            # Парсимо дату
            expire_dt = safe_parse_date(exp_str)
            exp_date = expire_dt.date() if isinstance(expire_dt, datetime) else expire_dt

            if exp_date >= today:
                # PRO дійсний — повертаємо дату
                return {"isPro": True, "expire_date": exp_str.strip()}

            # Прострочено — оновлюємо статус у таблиці
            sheet.values().update(
                spreadsheetId=os.getenv("SHEET_ID"),
                range=f"PRO!C{idx}",
                valueInputOption="RAW",
                body={"values": [["Не активовано"]]}
            ).execute()
            break  # далі не шукаємо

    return {"isPro": False, "expire_date": None}





@app.post("/clean-pro")
async def clean_pro_endpoint():
    from bot import clean_expired_pro
    try:
        clean_expired_pro()
        return {"success": True, "message": "Чистка PRO завершена"}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.api_route("/ping", methods=["GET", "HEAD"])
async def ping():
    return {"status": "alive"}

@app.post("/jobs/clean-requests")
async def job_clean_requests():
    """
    HTTP-ендпоінт для одноразового запуску очищення старих замовлень.
    Викликайте його CURL-ом або з GitHub Actions cron.
    """
    await clean_old_requests_once()
    return {"ok": True, "cleared": "old orders cleaned"}

@app.post("/jobs/delete-old-messages")
async def job_delete_old_messages():
    """
    Одноразово видаляє всі застарілі відеоповідомлення за даними з аркуша 'Видалення'.
    """
    await background_deleter_once()
    return {"ok": True, "deleted": "old messages removed"}


@app.post("/reactivate-user")
async def reactivate_user(req: Request):
    data = await req.json()
    user_id = str(data.get("user_id"))

    print(f"✅ Користувач {user_id} знову активний")
    return {"ok": True}
    



@app.post("/rate")
async def rate_film(data: RateRequest):
    try:
        print("🔔 /rate запит отримано:", data.dict())

        film_name = data.film_name
        action = data.action
        undo_action = data.undo

        SPREADSHEET_ID = os.getenv("SHEET_ID")
        if not SPREADSHEET_ID:
            return JSONResponse(status_code=500, content={"success": False, "error": "SHEET_ID не визначено"})

        service = get_google_service()
        sheet = service.spreadsheets()
        values = sheet.values().get(
            spreadsheetId=SPREADSHEET_ID,
            range="Sheet1!A2:Z1000"
        ).execute().get("values", [])

        col_idx = 12 if action == "like" else 13
        undo_col_idx = 12 if undo_action == "like" else 13 if undo_action == "dislike" else None

        updates = []

        found = False
        for idx, row in enumerate(values, start=2):
            if len(row) == 0 or row[0].strip().lower() != film_name.strip().lower():
                continue

            found = True
            while len(row) <= max(col_idx, undo_col_idx if undo_col_idx is not None else 0):
                row.append("0")

            current = int(row[col_idx]) if row[col_idx].isdigit() else 0
            current += 1

            updates.append({
                "range": f"Sheet1!{chr(65+col_idx)}{idx}",
                "values": [[str(current)]]
            })

            if undo_col_idx is not None:
                undo_val = int(row[undo_col_idx]) if row[undo_col_idx].isdigit() else 0
                undo_val = max(0, undo_val - 1)
                updates.append({
                    "range": f"Sheet1!{chr(65+undo_col_idx)}{idx}",
                    "values": [[str(undo_val)]]
                })

        if not found:
            print("❌ Фільм не знайдено у таблиці")
            return JSONResponse(status_code=404, content={"success": False, "error": "Фільм не знайдено"})

        # ✅ Надсилаємо всі оновлення за один раз
        print("🔃 Оновлення Google Sheet:", updates)
        sheet.values().batchUpdate(
            spreadsheetId=SPREADSHEET_ID,
            body={
                "valueInputOption": "USER_ENTERED",
                "data": updates
            }
        ).execute()

        return {"success": True}

    except Exception as e:
        print(f"❌ Помилка в /rate: {e}")
        return JSONResponse(status_code=500, content={"success": False, "error": "Внутрішня помилка сервера"})

from pytz import timezone
from datetime import datetime
import asyncio
import os
from google_api import get_google_service
from bot import bot
# ── ID приватного каналу-репозиторію з фільмами
MEDIA_CHANNEL_ID = int(os.getenv("MEDIA_CHANNEL_ID"))


async def notify_pro_expiring():
    service = get_google_service()
    sheet = service.spreadsheets()
    kyiv = timezone("Europe/Kyiv")

    while True:
        print("🔔 Перевірка PRO, кому треба нагадати...")

        data = sheet.values().get(
            spreadsheetId=os.getenv("SHEET_ID"),
            range="PRO!A2:E1000"
        ).execute().get("values", [])

        now = datetime.now(kyiv)

        for i, row in enumerate(data):
            if len(row) < 4:
                continue

            user_id, username, status, expire_str = row[:4]
            notified = row[4] if len(row) > 4 else ""
            if status != "Активно":
                continue
            try:
                # Розбираємо будь-яку ISO-дату з часовим поясом або без
                expire_date = dateutil.parser.isoparse(expire_str)
                # Переводимо в київський час
                if expire_date.tzinfo is None:
                    expire_date = kyiv.localize(expire_date)
                else:
                    expire_date = expire_date.astimezone(kyiv)
                # Якщо була лише дата без часу — встаємо на 23:59:00
                if len(expire_str.strip()) == 10:
                    expire_date = expire_date.replace(hour=23, minute=59, second=0)
            except Exception as e:
                print(f"Помилка парсингу дати {expire_str}: {e}")
                continue
          
                    

            hours_left = (expire_date - now).total_seconds() / 3600

            if 0 < hours_left <= 48 and notified != "yes":
                try:
                    await bot.send_message(
                        int(user_id),
                        f"⚡️ Ваш PRO-доступ закінчиться {expire_date.strftime('%d.%m.%Y %H:%M')}!\n\n"
                        "🔄 Продовжіть PRO, щоб не втратити доступ до фільмів!"
                    )
                    row_number = i + 2
                    sheet.values().update(
                        spreadsheetId=os.getenv("SHEET_ID"),
                        range=f"PRO!E{row_number}",
                        valueInputOption="RAW",
                        body={"values": [["yes"]]}
                    ).execute()
                    print(f"✅ Оповістили {user_id}")
                except Exception as e:
                    print(f"❌ Не вдалося надіслати нагадування {user_id}: {e}")

        await asyncio.sleep(60 * 60 * 2)  # раз на 2 години

@app.post("/notify-repair-done")
async def notify_repair_done():
    """
    Розсилає повідомлення всім користувачам із таблиці PRO
    про завершення ремонтних робіт і нову систему перегляду.
    """
    service = get_google_service()
    sheet = service.spreadsheets()

    # 📋 Отримуємо всіх користувачів із аркуша PRO
    rows = sheet.values().get(
        spreadsheetId=os.getenv("SHEET_ID"),
        range="PRO!A2:D1000"
    ).execute().get("values", [])

    notified = 0

    for row in rows:
        if not row or len(row) < 1:
            continue
        user_id = row[0]
        if not user_id.isdigit():
            continue

        try:
            await bot.send_message(
                int(user_id),
                "✅ Роботи завершено!\n\n"
                "🎬 Ми оновили систему перегляду фільмів — тепер усе працює ще швидше й зручніше 😎\n\n"
                "🔄 Раніше фільм надходив особисто від бота, а тепер він відкривається прямо через наші кіно-канали 📺\n"
                "🚀 Перегляд став стабільним — без зависань, глюків і збоїв 💪\n\n"
                "🍿 Приємного кіно! ❤️"
            )
            notified += 1
            await asyncio.sleep(0.1)
        except Exception as e:
            print(f"⚠️ Не вдалося надіслати {user_id}: {e}")

    print(f"✅ Розсилку завершено — повідомлено {notified} користувачів.")
    return {"ok": True, "sent": notified}

