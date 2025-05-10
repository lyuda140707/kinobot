from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Request
from aiogram import types
from bot import dp, bot
from google_api import get_gsheet_data, save_statistics  # імпорт обох функцій
import os
import requests
import gspread
import json

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
    
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # або вкажи конкретне джерело
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

# ✅ ОНОВЛЕНА функція тільки одна:
@app.post("/search-in-bot")
async def search_in_bot(request: Request):
    data = await request.json()
    user_id = data.get("user_id")
    query = data.get("query", "").lower()

    if not user_id or not query:
        return {"found": False}

    save_statistics(user_id)  # 🆕 Додаємо користувача в статистику

    films = get_gsheet_data()

    for film in films:
        if query in film.get("Назва", "").lower():
            video_url = film.get("Посилання")
            if video_url:
                return {"found": True, "videoUrl": video_url}
            else:
                return {"found": False}

    return {"found": False}
