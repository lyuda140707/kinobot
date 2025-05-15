from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Request, HTTPException
from aiogram import types
from bot import dp, bot
from google_api import get_gsheet_data
import os
import requests
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
import asyncio

app = FastAPI()

- @app.get("/send-channel-post")
+ @app.post("/send-channel-post")
    token = os.getenv("BOT_TOKEN")
    channel_id = os.getenv("CHANNEL_ID")  # або напряму ID твого каналу
    webapp_url = "https://lyuda140707.github.io/kinobot-webapp/"

    message_text = "🎬 Відкрити кіно-застосунок"

    payload = {
        "chat_id": channel_id,
        "text": message_text,
        "reply_markup": {
            "inline_keyboard": [[
                {"text": "🎬 Перейти в застосунок", "web_app": {"url": webapp_url}}
            ]]
        }
    }

    response = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json=payload)
    
    if response.status_code == 200:
        return {"status": "✅ Повідомлення надіслано!"}
    else:
        return {"status": "❌ Помилка", "details": response.text}


@app.post("/request-film")
async def request_film(req: Request):
    data = await req.json()
    user_id = data.get('user_id')
    film_name = data.get('film_name')
    
    if user_id and film_name:
        message = f"🎬 Користувач {user_id} хоче додати фільм: {film_name}"
        requests.post(f"https://api.telegram.org/bot7749808687:AAGQ2TuCvI5T-HfRFP7GxWAsXsCi15Heqek/sendMessage", data={
            "chat_id": "7205633024",
            "text": message
        })
    return {"ok": True}

@app.on_event("startup")
async def on_startup():
    webhook_url = os.getenv("WEBHOOK_URL")
    if webhook_url:
        await bot.set_webhook(webhook_url)

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

@app.post("/send-film")
async def send_film(request: Request):
    data = await request.json()
    user_id = data.get("user_id")
    film_name = data.get("film_name")

    if not user_id or not film_name:
        raise HTTPException(status_code=400, detail="user_id або film_name відсутні")

    films = get_gsheet_data()

    found_film = None
    for film in films:
        if film_name.lower() in film.get("Назва", "").lower() and film.get("file_id"):
            found_film = film
            break

    if not found_film:
        return {"success": False, "error": "Фільм не знайдено або немає file_id"}

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="🎥 Обрати інший фільм 📚",
                web_app=WebAppInfo(url="https://lyuda140707.github.io/kinobot-webapp/")
            )]
        ]
    )

    sent_message = await bot.send_video(
        chat_id=user_id,
        video=found_film["file_id"],
        caption="🎬 Приємного перегляду! 🍿",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

    # ✅ Одразу повертаємо відповідь WebApp'у
    asyncio.create_task(delete_after_timeout(user_id, sent_message.message_id))

    return {"success": True}


# окремо виносимо функцію видалення
async def delete_after_timeout(chat_id, message_id):
    await asyncio.sleep(10800)  # 3 години = 60*60*3 = 10800 секунд
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
        print(f"✅ Повідомлення {message_id} видалено")
    except Exception as e:
        print(f"❗️ Помилка видалення повідомлення: {e}")

@app.post("/check-subscription")
async def check_subscription(request: Request):
    data = await request.json()
    user_id = data.get('user_id')

    if not user_id:
        raise HTTPException(status_code=400, detail="user_id відсутній")

    bot_token = os.getenv("BOT_TOKEN")  # Бере токен з .env
    channel_username = "@KinoTochkaUA"  # Твій канал

    url = f"https://api.telegram.org/bot{bot_token}/getChatMember"
    params = {
        "chat_id": channel_username,
        "user_id": user_id
    }
    response = requests.get(url, params=params)
    result = response.json()

    if result.get("ok") and result["result"]["status"] in ["member", "administrator", "creator"]:
        return {"subscribed": True}
    else:
        return {"subscribed": False}


# Додаємо CORS для доступу WebApp
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Або конкретні домени, якщо треба безпечніше
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
