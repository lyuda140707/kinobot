from fastapi import FastAPI, Request
from aiogram import types
from bot import dp, bot
from google_api import get_gsheet_data
import os

app = FastAPI()

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

@app.post("/telegram-search")
async def telegram_search(request: Request):
    data = await request.json()
    user_id = data.get("user_id")
    query = data.get("query", "").lower()

    if not user_id or not query:
        return {"error": "Missing data"}

    films = get_gsheet_data()
    for film in films:
        if query in film.get("Назва", "").lower():
            title = film.get("Назва", "Без назви")
            desc = film.get("Опис", "")
            file_id = film.get("file_id")

            caption = f"*🎬 {title}*\n{desc}"
            if file_id:
                await bot.send_video(chat_id=user_id, video=file_id, caption=caption, parse_mode="Markdown")
            else:
                await bot.send_message(chat_id=user_id, text=caption, parse_mode="Markdown")
            return {"ok": True}

    await bot.send_message(chat_id=user_id, text="Фільм не знайдено 😢")
    return {"ok": True}
