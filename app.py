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
import dateutil.parser
from google_api import add_user_if_not_exists
from fastapi import HTTPException
from pydantic import BaseModel
from typing import Optional
from fastapi import Body
from pro_utils import has_active_pro
from utils.date_utils import safe_parse_date
from google_api import fetch_with_retry
import logging
from fastapi.responses import JSONResponse

service = get_google_service()
sheet = service.spreadsheets()

logging.getLogger('googleapiclient.discovery_cache').setLevel(logging.ERROR)

class RateRequest(BaseModel):
    film_name: str
    action: str            # наприклад, "like" або "dislike"
    undo: Optional[str] = None  # опціональне, "like" або "dislike" або None

class SearchRequest(BaseModel):
    user_id: int
    query: str
    username: Optional[str] = None
    first_name: Optional[str] = None



# Список повідомлень, які потрібно буде видалити
messages_to_delete = []


from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 background_deleter запущено!")
    webhook_url = os.getenv("WEBHOOK_URL")
    if webhook_url:
        await bot.set_webhook(webhook_url)

    asyncio.create_task(clean_old_requests())
    print("✅ Задача clean_old_requests стартувала")


    asyncio.create_task(background_deleter())
    print("✅ Задача background_deleter стартувала")

    asyncio.create_task(check_pending_payments())
    print("✅ Задача check_pending_payments стартувала")

    yield

    

# ✅ Оголошення FastAPI ДО використання декораторів
app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://lyuda140707.github.io",   # твій фронтенд-домен
        # тут можна додати інші домени, наприклад, для локального тесту:
        # "http://localhost:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)




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
    await bot.send_message(
        admin_id, 
        f"💳 Користувач [{first_name}](tg://user?id={user_id}) натиснув 'Я оплатив'\n\n✅ Щоб підтвердити PRO, надішли:\n`/ok {user_id}`",
        parse_mode="Markdown"
    )

    return {"ok": True}





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

            SHEET_ID = os.getenv("SHEET_ID")
            result = fetch_with_retry(service, SHEET_ID, "Замовлення!A2:C1000").get("values", [])

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
        requests.post(
            f"https://api.telegram.org/bot{os.getenv('BOT_TOKEN')}/sendMessage",
            data={"chat_id": os.getenv("ADMIN_ID", "7963871119"), "text": message}
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

@app.post("/search-in-bot")
async def search_in_bot(data: SearchRequest):
    user_id = data.user_id
    query = data.query.lower()
    username = data.username or ""
    first_name = data.first_name or ""

    if user_id:
        add_user_if_not_exists(user_id, username, first_name)

    if not user_id or not query:
        return {"found": False}

    films = get_gsheet_data()

    found_film = None
    for film in films:
        if query in film.get("Назва", "").lower() and film.get("Посилання"):
            found_film = film
            break

    if found_film:
        return {"found": True, "videoUrl": found_film["Посилання"]}
    else:
        return {"found": False}

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

        films = get_gsheet_data()

        found_film = None
        for film in films:
            if film_name.lower() in film.get("Назва", "").lower() and film.get("file_id"):
                found_film = film
                break

        if not found_film:
            return JSONResponse(status_code=404, content={"success": False, "error": "Фільм не знайдено або немає file_id"})

                # 🔒 Перевірка доступу PRO
        if found_film.get("Доступ") == "PRO" and not has_active_pro(str(user_id)):
            return JSONResponse(status_code=403, content={"success": False, "error": "⛔ Доступ лише для PRO користувачів"})


        # Готуємо клавіатуру
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(
                    text="🎥 Обрати інший фільм 📚",
                    web_app=WebAppInfo(url="https://lyuda140707.github.io/kinobot-webapp/")
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

        # Надсилаємо відео
        sent_message = await bot.send_video(
            chat_id=user_id,
            video=found_film["file_id"],
            caption=caption,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )

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
    file_id = data.get("file_id")

    print(f"📽️ /send-film-id {file_id} від {user_id}")

    films = get_gsheet_data()  # ⬅️ додай це перед пошуком
    found_film = next((f for f in films if f.get("file_id") == file_id), None)

    if not found_film:
        return {"success": False, "error": "Фільм не знайдено"}

    # 🔒 Захист PRO
    if found_film.get("Доступ") == "PRO" and not has_active_pro(user_id):
        return {"success": False, "error": "⛔ Доступ лише для PRO користувачів"}

    caption = f"🎬 {found_film.get('Назва', '')}\n\n{found_film.get('Опис', '')}".strip()

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="🎥 Обрати інший фільм 📚",
                web_app=WebAppInfo(url="https://lyuda140707.github.io/kinobot-webapp/")
            )]
        ]
    )

    try:
        # Надсилаємо відео
        sent_message = await bot.send_video(
            chat_id=user_id,
            video=file_id,
            caption=caption,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

        # Зберігаємо для видалення
        service = get_google_service()
        sheet = service.spreadsheets()

        kyiv = timezone("Europe/Kyiv")
        delete_time = datetime.now(kyiv) + timedelta(hours=24)

        sheet.values().append(
            spreadsheetId=os.getenv("SHEET_ID"),
            range="Видалення!A2",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values": [[str(user_id), str(sent_message.message_id), delete_time.isoformat()]]}
        ).execute()

        return {"success": True}

    except Exception as e:
        print(f"❌ Помилка надсилання: {e}")
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
        response = fetch_with_retry(service, os.getenv("SHEET_ID"), "Видалення!A2:C1000")
        data = response.get("values", [])
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
                    
        await asyncio.sleep(60)
        
async def clean_old_requests():
    service = get_google_service()
    sheet = service.spreadsheets()
    kyiv = timezone("Europe/Kyiv")
    SHEET_ID = os.getenv("SHEET_ID")

    while True:
        try:
            print("🧹 Очищення старих замовлень...")

            # тут правильний відступ і get("values", [])
            existing_ids = [row[0] for row in fetch_with_retry(service, SHEET_ID, "Користувачі!A2:A1000").get("values", []) if row]

            now = datetime.now(kyiv)
            updated_rows = []

            # ! Тут треба отримати всі записи з аркуша "Замовлення"
            result = fetch_with_retry(service, SHEET_ID, "Замовлення!A2:C10000").get("values", [])

            for i, row in enumerate(result):
                if len(row) < 3:
                    continue
                try:
                    row_date = kyiv.localize(datetime.strptime(row[2], "%Y-%m-%d %H:%M:%S"))
                    if (now - row_date).days > 31:
                        # Замінити рядок на порожній
                        row_num = i + 2
                        updated_rows.append(f"Замовлення!A{row_num}:C{row_num}")
                except Exception as e:
                    print(f"⚠️ Помилка дати в рядку {i+2}: {e}")

            for rng in updated_rows:
                sheet.values().update(
                    spreadsheetId=os.getenv("SHEET_ID"),
                    range=rng,
                    valueInputOption="RAW",
                    body={"values": [["", "", ""]]}
                ).execute()

            print(f"🗑️ Видалено {len(updated_rows)} записів")

        except Exception as e:
            print(f"❌ Помилка в clean_old_requests: {e}")

        await asyncio.sleep(3600 * 6)  # перевірка кожні 6 годин


async def check_pending_payments():
    service = get_google_service()
    sheet = service.spreadsheets()

    kyiv = timezone("Europe/Kyiv")

    while True:
        print("🔎 Перевірка очікуючих платежів...")  
        now = datetime.now(kyiv)  # aware datetime (з таймзоною)
        print(f"🕒 Поточний час: {now}")

        response = fetch_with_retry(service, os.getenv("SHEET_ID"), "PRO!A2:D")
        rows = response.get("values", [])

        print(f"📋 Знайдено записів для перевірки: {len(rows)}")

        for i, row in enumerate(rows):
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

                # Якщо created_at naive — локалізуємо в Kyiv timezone:
                if created_at.tzinfo is None:
                    created_at = kyiv.localize(created_at)

                print(f"⏰ Запис створений о: {created_at}")
            except Exception as e:
                print(f"⚠️ Помилка формату дати '{created_at_str}': {e}")
                continue

            diff = now - created_at
            print(f"⏳ Пройшло часу: {diff}")

            if diff > timedelta(minutes=10):
                # решта твого коду (повідомлення, оновлення статусу...)
                pass

        await asyncio.sleep(60)


@app.post("/check-pro")
async def check_pro(req: Request):
    data = await req.json()
    user_id = str(data.get("user_id"))

    service = get_google_service()
    sheet = service.spreadsheets()

    response = fetch_with_retry(service, os.getenv("SHEET_ID"), "PRO!A2:D")
    rows = response.get("values", [])

    kyiv = timezone("Europe/Kyiv")
    now = datetime.now(kyiv)  # aware datetime

    for i, row in enumerate(rows):
        if len(row) < 4:
            continue

        row_user_id = row[0].strip()
        status = row[2].strip()
        expire_str = row[3].strip()

        if row_user_id == user_id:
            try:
                expire_date = safe_parse_date(expire_str)

                # Якщо expire_date naive, робимо aware:
                if expire_date.tzinfo is None:
                    expire_date = kyiv.localize(expire_date)

                if status == "Активно" and expire_date > now:
                    return {"isPro": True, "expire_date": expire_str}
                elif status == "Активно" and expire_date <= now:
                    row_number = i + 2
                    sheet.values().update(
                        spreadsheetId=os.getenv("SHEET_ID"),
                        range=f"PRO!C{row_number}:C{row_number}",
                        valueInputOption="RAW",
                        body={"values": [["Не активовано"]]}
                    ).execute()
                    print(f"⛔ PRO закінчився для {user_id} — статус оновлено")
            except Exception as e:
                print(f"⚠️ Помилка розпізнавання дати {expire_str} — {e}")

    return {"isPro": False}




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
@app.post("/reactivate-user")
async def reactivate_user(req: Request):
    data = await req.json()
    user_id = str(data.get("user_id"))

    print(f"✅ Користувач {user_id} знову активний")
    return {"ok": True}
    


from fastapi.responses import JSONResponse

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
        SHEET_ID = os.getenv("SHEET_ID")
        if not SHEET_ID:
            return JSONResponse(status_code=500, content={"success": False, "error": "SHEET_ID не визначено"})


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
