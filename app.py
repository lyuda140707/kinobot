from fastapi import FastAPI, Request
from aiogram import types
from bot import dp, bot
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
    query = data.get("query")

    if not user_id or not query:
        return {"error": "Missing user_id or query"}

    # Надішли відповідь у Telegram
    text = f"🔍 Ви шукали: *{query}*\nСпробуйте ще раз у боті або натисніть /start"
    await bot.send_message(chat_id=user_id, text=text, parse_mode="Markdown")

    return {"ok": True}
