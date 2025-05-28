from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Request, HTTPException
from aiogram import types
from bot import dp, bot
from google_api import get_gsheet_data
import os
import requests
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
import asyncio
from datetime import datetime, timedelta
import json
from pytz import timezone

# Список повідомлень, які потрібно буде видалити
messages_to_delete = []


app = FastAPI()



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
    print("🚀 background_deleter запущено!")

    webhook_url = os.getenv("WEBHOOK_URL")
    if webhook_url:
        await bot.set_webhook(webhook_url)

    asyncio.create_task(background_deleter())


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

    # Час видалення через 3 години
    kyiv = timezone("Europe/Kyiv")
    kyiv = timezone("Europe/Kyiv")
    delete_time = datetime.now(kyiv) + timedelta(hours=12)
    delete_time_kyiv = delete_time.astimezone(kyiv)
    delete_time_str = delete_time_kyiv.strftime('%H:%M %d.%m')

    # Підпис до повідомлення
    caption = (
        "🎬 Приємного перегляду! 🍿\n\n"
        f"🕓 Це повідомлення буде видалено о {delete_time_str} (за Києвом)."
    )

    sent_message = await bot.send_video(
        chat_id=user_id,
        video=found_film["file_id"],
        caption=caption,
        reply_markup=keyboard,
        parse_mode="Markdown"
    )



    print(f"📩 Додано повідомлення до видалення: chat_id={user_id}, message_id={sent_message.message_id}")
    print(f"🕓 Видалення заплановано на: {delete_time.isoformat()}")

    messages_to_delete.append({
        "chat_id": user_id,
        "message_id": sent_message.message_id,
        "delete_at": delete_time
    })




    # Зберігаємо у файл (convert datetime to string)
    with open("deleter.json", "w") as f:
        json.dump(messages_to_delete, f, default=str)

    return {"success": True}






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

async def background_deleter():
    # 🔁 Відновити список повідомлень з файлу, якщо він існує
    if os.path.exists("deleter.json"):
        with open("deleter.json", "r") as f:
            data = json.load(f)
            for item in data:
                item["delete_at"] = datetime.fromisoformat(item["delete_at"]).replace(tzinfo=timezone("Europe/Kyiv"))
            messages_to_delete.extend(data)
        print(f"♻️ Відновлено {len(messages_to_delete)} повідомлень до видалення")

    while True:
        now = datetime.now(timezone("Europe/Kyiv"))
        print(f"⏳ Перевірка на видалення: {len(messages_to_delete)} в черзі")

        to_delete = [msg for msg in messages_to_delete if msg["delete_at"] <= now]

        for msg in to_delete:
            print(f"🗑 Видаляю повідомлення {msg['message_id']} у чаті {msg['chat_id']}")
            try:
                await bot.delete_message(chat_id=msg["chat_id"], message_id=msg["message_id"])
                print(f"✅ Видалено повідомлення {msg['message_id']}")
            except Exception as e:
                print(f"❗️ Помилка при видаленні повідомлення {msg['message_id']}: {e}")

            messages_to_delete.remove(msg)

            # 🔄 Оновлюємо файл після кожного видалення
            with open("deleter.json", "w") as f:
                json.dump(messages_to_delete, f, default=str)

        await asyncio.sleep(60)


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
