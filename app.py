from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Request
from aiogram import types
from bot import dp, bot
from google_api import get_gsheet_data
import os
from fastapi import FastAPI, Request
from fastapi import HTTPException
import requests


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

    for film in films:
        if query in film.get("Назва", "").lower():
            video_url = film.get("Посилання")
            if video_url:
                return {"found": True, "videoUrl": video_url}
            else:
                return {"found": False}

    return {"found": False}

@app.post("/send-film")
async def send_film(request: Request):
    data = await request.json()
    user_id = data.get("user_id")
    film_name = data.get("film_name")

    if not user_id or not film_name:
        raise HTTPException(status_code=400, detail="user_id або film_name відсутні")

    films = get_gsheet_data()

    for film in films:
        if film_name.lower() in film.get("Назва", "").lower():
            file_id = film.get("file_id")
            if file_id:
                caption = f"🎬 *{film['Назва']}*\n{film['Опис']}"
                await bot.send_video(
                    chat_id=user_id,
                    video=file_id,
                    caption=caption,
                    parse_mode="Markdown"
                )
                return {"success": True}
            else:
                return {"success": False, "error": "file_id відсутній для цього фільму"}

    return {"success": False, "error": "Фільм не знайдено"}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # або вкажи конкретне джерело, якщо треба безпечно
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

