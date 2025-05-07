from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Request
from aiogram import types
from bot import dp, bot
from google_api import get_gsheet_data
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # або вкажи конкретне джерело, якщо треба безпечно
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


