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


# Список повідомлень, які потрібно буде видалити
messages_to_delete = []


from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 background_deleter запущено!")
    webhook_url = os.getenv("WEBHOOK_URL")
    if webhook_url:
        await bot.set_webhook(webhook_url)

    asyncio.create_task(background_deleter())
    print("✅ Задача background_deleter стартувала")

    asyncio.create_task(check_pending_payments())
    print("✅ Задача check_pending_payments стартувала")

    yield

    

# ✅ Оголошення FastAPI ДО використання декораторів
app = FastAPI(lifespan=lifespan)


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

    sheet.values().append(
    spreadsheetId=os.getenv("SHEET_ID"),
    range="PRO!A2:D2",
    valueInputOption="USER_ENTERED",
    body={"values": [[str(user_id), username, "Очікує підтвердження", datetime.now().strftime("%Y-%m-%d %H:%M:%S")]]}
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
        user_id = data.get('user_id')
        film_name = data.get('film_name')

        if not user_id or not film_name:
            return JSONResponse(status_code=400, content={"success": False, "error": "user_id або film_name відсутні"})

        message = f"🎬 Користувач {user_id} хоче додати фільм: {film_name}"

        telegram_response = requests.post(
            f"https://api.telegram.org/bot{os.getenv('BOT_TOKEN')}/sendMessage",
            data={"chat_id": "7963871119", "text": message}
        )

        # Якщо не вдалося надіслати повідомлення
        if telegram_response.status_code != 200:
            return JSONResponse(status_code=500, content={"success": False, "error": "Помилка при надсиланні до Telegram"})

        return {"success": True}

    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})





@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    update = types.Update(**data)
    await dp.feed_update(bot, update)
    return {"ok": True}

@app.post("/search-in-bot")
async def search_in_bot(request: Request):
    data = await request.json()
    user_id = data.get("user_id")
    query = data.get("query", "").lower()

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

        print(f"⏳ Перевірка на видалення: {len(data)} в черзі")

        for i, row in enumerate(data):
            if len(row) < 3:
                continue

            user_id = row[0]
            message_id = row[1]
            delete_at_str = row[2]

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

async def check_pending_payments():
    service = get_google_service()
    sheet = service.spreadsheets()

    while True:
        print("🔎 Перевірка очікуючих платежів...")  # Додали діагностику
        now = datetime.now()

        data = sheet.values().get(
            spreadsheetId=os.getenv("SHEET_ID"),
            range="PRO!A2:D1000"
        ).execute().get("values", [])

        print(f"Знайдено записів: {len(data)}")

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
                # Обробка двох можливих форматів дати
                if len(created_at_str) == 10:
                    created_at = datetime.strptime(created_at_str, "%Y-%m-%d")
                else:
                    created_at = datetime.strptime(created_at_str, "%Y-%m-%d %H:%M:%S")
            except Exception as e:
                print(f"⚠️ Некоректна дата: {created_at_str} — {e}")
                continue

            if (now - created_at) > timedelta(minutes=10):
                from bot import safe_send
                print(f"⚠️ Термін очікування вийшов для користувача {user_id}")

                try:
                    await safe_send(bot, int(user_id),
                        "❗️ Ми не знайшли вашу оплату за PRO доступ.\n\n"
                        "Можливо, ви забули оплатити або оплата ще обробляється.\n"
                        "Спробуйте повторити або натисніть кнопку нижче:",
                        reply_markup=InlineKeyboardMarkup(
                            inline_keyboard=[[
                                InlineKeyboardButton(
                                    text="🚀 Повторити оплату",
                                    web_app=WebAppInfo(url="https://lyuda140707.github.io/kinobot-webapp/")
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


@app.post("/check-pro")
async def check_pro(req: Request):
    data = await req.json()
    user_id = str(data.get("user_id"))

    service = get_google_service()
    sheet = service.spreadsheets()

    req = sheet.values().get(
        spreadsheetId=os.getenv("SHEET_ID"),
        range="PRO!A2:D1000"
    ).execute()

    rows = req.get("values", [])

    for row in rows:
        if len(row) < 4:
            continue

        row_user_id = row[0].strip()
        status = row[2].strip()
        expire_str = row[3].strip()

        if row_user_id == user_id and status == "Активно":
            try:
                expire_date = datetime.strptime(expire_str, "%Y-%m-%d")
                if expire_date > datetime.now():
                    return {"isPro": True, "expire_date": expire_str}
            except Exception as e:
                print(f"⚠️ Помилка формату дати в PRO: {expire_str} — {e}")
                continue

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



# Додаємо CORS для доступу WebApp
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Або конкретні домени, якщо треба безпечніше
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
