from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Request, HTTPException
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
# 🧩 Перевірка доступу до Supabase при старті сервера
from supabase_api import SUPABASE_URL, SUPABASE_KEY
from fastapi.responses import PlainTextResponse
import requests
from fastapi import Header

print("🧩 Testing Supabase connection...")
try:
    url = f"{SUPABASE_URL}/rest/v1/films?select=message_id&limit=1"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    }
    r = requests.get(url, headers=headers, timeout=10)
    if r.status_code == 200:
        print("✅ Supabase доступний — з’єднання працює.")
    else:
        print(f"⚠️ Supabase відповів помилкою ({r.status_code}): {r.text}")
except Exception as e:
    print(f"❌ Немає доступу до Supabase: {e}")



# ==== Supabase REST helper ====
SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = (
    os.getenv("SUPABASE_SERVICE_KEY")
    or os.getenv("SUPABASE_KEY")
    or os.getenv("SUPABASE_ANON_KEY")
    or ""
)

def _sb_headers():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("Supabase URL/KEY не задані в ENV")
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
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
    sheet = get_google_service().spreadsheets()

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
async def lifespan(app):
    # ❌ ВИМКНЕНО: чистка PRO на старті (вбиває інстанс по RAM)
    # from bot import clean_expired_pro
    # await asyncio.to_thread(clean_expired_pro)

    yield


    

# ✅ Оголошення FastAPI ДО використання декораторів
app = FastAPI(lifespan=lifespan)
import time
import httpx

_last_admin_ping = 0.0

async def notify_admin(text: str):
    global _last_admin_ping

    token = os.getenv("BOT_TOKEN", "").strip()
    chat_id = os.getenv("ADMIN_ID", "").strip()

    if not token or not chat_id:
        return

    now = time.time()
    if now - _last_admin_ping < 10:
        return
    _last_admin_ping = now

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": text[:3500],
                    "disable_web_page_preview": True
                }
            )
    except Exception:
        pass
# === 🧩 Подача статичних файлів та сторінки профілю ===
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

# створюємо папку, якщо її немає
os.makedirs("static", exist_ok=True)

# монтуємо статичні файли
app.mount("/static", StaticFiles(directory="static"), name="static")

# маршрут для /profile.html
@app.get("/profile.html", include_in_schema=False)
async def serve_profile():
    return FileResponse("static/profile.html")


# 🛡️ Безпечні HTTP-заголовки
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"               # не дозволяє вбудовувати у iframe
    response.headers["X-Content-Type-Options"] = "nosniff"     # блокує MIME-атаки
    response.headers["Referrer-Policy"] = "no-referrer"        # не передає URL між сайтами
    response.headers["Permissions-Policy"] = "geolocation=()"  # заборона на доступ до гео/камери
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


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
@app.get("/robots.txt")
async def robots():
    return PlainTextResponse("User-agent: *\nDisallow: /\n")
    
@app.post("/notify-payment")
async def notify_payment(req: Request):
    data = await req.json()
    user_id = data.get("user_id")           # якщо користувач з Telegram
    web_id = data.get("web_id")             # якщо користувач із сайту без Telegram
    username = data.get("username", "")
    first_name = data.get("first_name", "")
    source = data.get("source", "unknown")  # від кого прийшов запит (site / webapp)

    # ✅ 1. Підключаємо Google Sheets
    service = get_google_service()
    sheet = service.spreadsheets()
    kyiv = timezone("Europe/Kyiv")
    now_kyiv = datetime.now(kyiv).strftime("%Y-%m-%d %H:%M:%S")

    # ✅ 2. Якщо користувач з Telegram (WebApp)
    if user_id:
        sheet.values().append(
            spreadsheetId=os.getenv("SHEET_ID"),
            range="PRO!A2:D2",
            valueInputOption="USER_ENTERED",
            body={"values": [[str(user_id), username, "Очікує підтвердження", now_kyiv]]}
        ).execute()

        admin_id = os.getenv("ADMIN_ID")
        await safe_send_admin(
            bot, admin_id,
            f"💳 Користувач [{first_name}](tg://user?id={user_id}) натиснув 'Я оплатив' ({source})\n\n"
            f"✅ Щоб підтвердити PRO, надішли:\n`/ok {user_id}`",
            parse_mode="Markdown"
        )
        return {"ok": True}

    # ✅ 3. Якщо користувач із сайту (без Telegram)
    elif web_id:
        sheet.values().append(
            spreadsheetId=os.getenv("SHEET_ID"),
            range="PRO!A2:D2",
            valueInputOption="USER_ENTERED",
            body={"values": [[str(web_id), "WEB", "Очікує підтвердження", now_kyiv]]}
        ).execute()

        admin_id = os.getenv("ADMIN_ID")
        await safe_send_admin(
            bot, admin_id,
            f"💳 Новий запит на оплату через САЙТ ({source})\n🌐 WEB-ID: `{web_id}`\n\n"
            "Щоб активувати, додай цей WEB-ID у Google Таблицю (лист PRO).",
            parse_mode="Markdown"
        )
        return {"ok": True}

    # ❌ Якщо обидва відсутні — повертаємо помилку
    else:
        raise HTTPException(status_code=400, detail="user_id або web_id відсутній")


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
        # 🛡️ АНТИ-СПАМ (бан за викачування)
        from anti_spam import check_limit
        ok, ban_until = check_limit(int(user_id), has_active_pro(str(user_id)))
        if not ok:
            return JSONResponse(
                status_code=403,
                content={
                    "success": False,
                    "error": f"⛔ Ви тимчасово заблоковані до {ban_until.strftime('%H:%M %d.%m')} через масові завантаження."
                }
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
    data = await request.json()
    user_id = str(data.get("user_id"))
    message_id = str(data.get("message_id", "")).strip()
    channel_in = str(data.get("channel_id", "")).strip()
    # 🛡️ Анти-спам: бан за масові скачування
    from anti_spam import check_limit
    is_ok, ban_until = check_limit(int(user_id), has_active_pro(user_id))
    
    if not is_ok:
        return {
            "success": False,
            "error": f"⛔ Ви тимчасово заблоковані до {ban_until.strftime('%H:%M %d.%m')} (масові завантаження без PRO)"
        }


    if not user_id or not message_id:
        return {"success": False, "error": "user_id або message_id відсутні"}

    print(f"📽️ /send-film-id {message_id} від {user_id}")
    print(f"    channel_in={channel_in}")

    # 🔍 Визначаємо, file_id це чи message_id
    try:
        row = None
        if len(message_id) > 20:
            print("🔍 Виявлено file_id — шукаємо по колонці file_id")
            rows = sb_find_by_file_and_channel(message_id, channel_in) if channel_in else sb_find_by_file_id(message_id)
        else:
            print("🔍 Виявлено message_id — шукаємо по колонці message_id")
            rows = sb_find_by_message_and_channel(message_id, channel_in) if channel_in else sb_find_by_message_id(message_id)
        if rows:
            row = rows[0]
    except Exception as e:
        print("❌ Помилка Supabase:", e)
        return {"success": False, "error": "Помилка доступу до бази"}

    if not row:
        return {"success": False, "error": "Фільм не знайдено"}

    # 🔒 Перевірка PRO
    if (row.get("access") == "PRO") and (not has_active_pro(user_id)):
        return {"success": False, "error": "⛔ Доступ лише для PRO користувачів"}

    title = row.get("title") or ""
    description = row.get("description") or ""
    caption = (
        f"🎬 {title}\n\n{description}\n\n"
        "🎞️🤩 Попкорн є? Світло вимкнено?\n"
        "🚀 Бо цей фільм точно не дасть засумувати!"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text="🎥 Обрати інший фільм 📚",
                web_app=WebAppInfo(url="https://relaxbox.site/")
            )
        ]]
    )

    try:
        channel_id = int(row.get("channel_id") or channel_in or os.getenv("MEDIA_CHANNEL_ID"))
        file_id = str(row.get("file_id", "")).strip()
        ADMIN_ID = int(os.getenv("ADMIN_ID", "941416029"))  # ← твій адмінський ID з ENV
        print(f"🧩 ADMIN_ID = {ADMIN_ID}")

        # 🧠 1️⃣ Основний спосіб — через file_id
        if file_id and len(file_id) > 20:
            print(f"🎬 Відправка через file_id={file_id} → {title}")
            try:
                sent_message = await bot.send_video(
                    chat_id=int(user_id),
                    video=file_id,
                    caption=caption,
                    reply_markup=keyboard,
                    parse_mode="HTML",
                    supports_streaming=True
                )
                print(f"⚡ Використано кешований file_id (миттєва відправка) → {title}")
                print(f"✅ Надіслано напряму через file_id ({user_id}) → {title}")
                # ⚙️ Telegram CDN warm-up — прискорюємо прогрузку сірої полоси
                try:
                    await asyncio.sleep(1)
                    await bot.send_chat_action(chat_id=int(user_id), action="upload_video")
                    print("⚙️ CDN warmed up для швидкого стріму ✅")
                except Exception as e:
                    print(f"⚠️ CDN warm-up error: {e}")
            except Exception as e:
                print(f"⚠️ Помилка send_video: {e}")
                # fallback — якщо file_id не спрацював
                if row.get("message_id"):
                    print("🔁 Використовуємо резервний copy_message()")
                    sent_message = await bot.copy_message(
                        chat_id=int(user_id),
                        from_chat_id=channel_id,
                        message_id=int(row.get("message_id"))
                    )
                    print(f"✅ Відправлено копією після помилки file_id ({user_id}) → {title}")
                else:
                    raise e
        else:
            # 🧩 2️⃣ Якщо file_id немає — резервна копія
            print(f"📦 Відправка копією (message_id={row.get('message_id')}) → {title}")
            sent_message = await bot.copy_message(
                chat_id=int(user_id),
                from_chat_id=channel_id,
                message_id=int(row.get("message_id"))
            )
            print(f"✅ Відправлено копією ({user_id}) → {title}")

            # 🧠 Потай отримуємо file_id через forward у ADMIN_ID (користувач цього не бачить)
            from supabase_api import sb_update_fileid_by_message_id
            try:
                await asyncio.sleep(1)  # коротка пауза

                fwd = await bot.forward_message(
                    chat_id=ADMIN_ID,
                    from_chat_id=channel_id,
                    message_id=int(row.get("message_id"))
                )

                if fwd.video and fwd.video.file_id:
                    new_file_id = fwd.video.file_id
                    print(f"🧠 Отримано новий file_id через ADMIN_ID: {new_file_id}")
                    sb_update_fileid_by_message_id(row.get("message_id"), new_file_id)
                    # прибираємо службову пересилку з адмін-чату
                    try:
                        await bot.delete_message(chat_id=ADMIN_ID, message_id=fwd.message_id)
                    except Exception as de:
                        print(f"⚠️ Не вдалося видалити службовий forward у ADMIN_ID: {de}")
                else:
                    print("⚠️ Не вдалося отримати video.file_id через forward до ADMIN_ID")

            except Exception as e:
                print(f"❌ Помилка при forward до ADMIN_ID: {e}")

        # 🕓 3️⃣ Запис у таблицю видалення
        kyiv = timezone("Europe/Kyiv")
        delete_time = datetime.now(kyiv) + timedelta(hours=24)
        sheet = get_google_service().spreadsheets()
        sheet.values().append(
            spreadsheetId=os.getenv("SHEET_ID"),
            range="Видалення!A2",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values": [[str(user_id), str(sent_message.message_id), delete_time.isoformat()]]}
        ).execute()

        print(f"🧾 Записано у 'Видалення' для користувача {user_id}")
        return {"success": True}

    except Exception as e:
        print(f"❌ Помилка надсилання: {e}")
    
        await notify_admin(
            f"❌ send-film-id помилка\n"
            f"user_id={user_id}\n"
            f"message_id={message_id}\n"
            f"{e}"
        )

    return {"success": False, "error": str(e)}
# ✅ Новий ендпоінт для віддачі stream_url у player.html
import httpx

@app.get("/stream/{film_id}")
async def get_stream_url(film_id: int):
    """Повертає stream_url для гравця (через service_role ключ)."""
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    }

    url = f"{SUPABASE_URL}/rest/v1/films?select=stream_url&id=eq.{film_id}"
    async with httpx.AsyncClient() as client:
        res = await client.get(url, headers=headers)

        if res.status_code != 200:
            return {"error": f"bad_response {res.status_code}"}

        data = res.json()
        if not data:
            return {"error": "not_found"}

        return {"stream_url": data[0].get("stream_url")}
# 🎬 Логування відкриття фільму на ТВ
@app.post("/log-tv")
async def log_tv(request: Request):
    data = await request.json()
    uid = data.get("uid")
    film_name = data.get("film_name")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"📺 [{now}] Користувач {uid} відкрив фільм на ТВ: {film_name}")
    return {"ok": True}


@app.post("/check-subscription")
async def check_subscription(request: Request):
    data = await request.json()
    user_id = data.get('user_id')

    if not user_id:
        raise HTTPException(status_code=400, detail="user_id відсутній")

    bot_token = os.getenv("BOT_TOKEN")

    # 🔹 Список каналів — два канали, без пробілів
    channels = ["@KinoTochkaFilms1", "@KinoTochkaUA"]

    subscribed_to_all = True  # вважаємо, що підписаний на всі

    for channel_username in channels:
        if not channel_username.strip():
            continue

        url = f"https://api.telegram.org/bot{bot_token}/getChatMember"
        params = {"chat_id": channel_username, "user_id": user_id}

        try:
            response = requests.get(url, params=params, timeout=10)
            result = response.json()
            if not (result.get("ok") and result["result"]["status"] in ["member", "administrator", "creator"]):
                subscribed_to_all = False
                print(f"❌ Не підписаний на {channel_username}")
                break
        except Exception as e:
            print(f"⚠️ Помилка перевірки {channel_username}: {e}")
            subscribed_to_all = False
            break

    return {"subscribed": subscribed_to_all}



async def background_deleter():
    service = get_google_service()
    sheet = service.spreadsheets()

    while True:
        from pytz import utc
        now = datetime.now(utc)

        try:
            # 🧾 Отримати всі записи з аркуша "Видалення"
            data = sheet.values().get(
                spreadsheetId=os.getenv("SHEET_ID"),
                range="Видалення!A2:C1000"
            ).execute().get("values", [])
        except TimeoutError:
            print("⚠️ Google Sheets timeout — повторна спроба через 30 сек.")
            await asyncio.sleep(30)
            continue
        except Exception as e:
            print(f"❌ Помилка запиту до Google Sheets: {e}")
            await asyncio.sleep(60)
            continue

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

                # 🧹 Очистити рядок після видалення
                row_number = i + 2
                try:
                    sheet.values().update(
                        spreadsheetId=os.getenv("SHEET_ID"),
                        range=f"Видалення!A{row_number}:C{row_number}",
                        valueInputOption="RAW",
                        body={"values": [["", "", ""]]}
                    ).execute()
                except Exception as e:
                    print(f"⚠️ Не вдалося очистити рядок {row_number}: {e}")

        # ⏳ Пауза перед наступною перевіркою
        await asyncio.sleep(60)

                    

        
async def background_deleter_once(limit: int = 80):
    from pytz import utc
    now = datetime.now(utc)

    # ✅ Ледаче створення клієнта (без глобального SHEETS)
    sheet = get_google_service().spreadsheets()

    rows = sheet.values().get(
        spreadsheetId=os.getenv("SHEET_ID"),
        range="Видалення!A2:C1000"
    ).execute().get("values", [])

    expired = []  # (row_num, user_id, message_id)

    for idx, row in enumerate(rows, start=2):
        if len(row) < 3:
            continue

        user_id, message_id, delete_at_str = row[0], row[1], row[2]

        if not (str(user_id).isdigit() and str(message_id).isdigit()):
            continue

        try:
            delete_at = dateutil.parser.isoparse(delete_at_str)
        except Exception:
            continue

        if now >= delete_at:
            expired.append((idx, int(user_id), int(message_id)))
            if len(expired) >= limit:
                break

    # 1) видаляємо повідомлення (по одному — норм)
    for row_num, user_id, message_id in expired:
        try:
            await bot.delete_message(chat_id=user_id, message_id=message_id)
        except Exception:
            pass

    # 2) чистимо рядки одним batchUpdate (а не 80 update в циклі)
    if expired:
        data = []
        for row_num, _, _ in expired:
            data.append({
                "range": f"Видалення!A{row_num}:C{row_num}",
                "values": [["", "", ""]]
            })

        sheet.values().batchUpdate(
            spreadsheetId=os.getenv("SHEET_ID"),
            body={"valueInputOption": "RAW", "data": data}
        ).execute()

    return {"deleted": len(expired)}

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
async def job_delete_old_messages(x_job_token: str = Header(default="")):
    if x_job_token != os.getenv("JOB_TOKEN", ""):
        raise HTTPException(status_code=401, detail="unauthorized")

    await background_deleter_once(limit=80)
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
