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
from fastapi.responses import JSONResponse
import dateutil.parser
from pro_utils import add_pro_user, is_pro_active


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
    yield

# ✅ Оголошення FastAPI ДО використання декораторів
app = FastAPI(lifespan=lifespan)
@app.get("/")
async def root():
    return {"status": "ok"}





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

@app.post("/check-pro")
async def check_pro(req: Request):
    data = await req.json()
    user_id = data.get("user_id")
    return {"isPro": is_pro_active(user_id)}

@app.post("/notify-payment")
async def notify_payment(req: Request):
    data = await req.json()
    user_id = data.get("user_id")
    add_pro_user(user_id)
    return {"status": "ok"}


@app.api_route("/ping", methods=["GET", "HEAD"])
async def ping():
    return {"status": "alive"}


# Додаємо CORS для доступу WebApp
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Або конкретні домени, якщо треба безпечніше
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
