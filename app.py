from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from aiogram import types
from bot import dp, bot, back_to_menu_keyboard
from google_api import get_gsheet_data
import os
import asyncio
import requests

# Оголошуємо FastAPI один раз
app = FastAPI()

@app.post("/send-video")
async def send_video(request: Request):
    data = await request.json()
    user_id = data.get("user_id")
    file_id = data.get("file_id")

    if not user_id or not file_id:
        return {"success": False}

    try:
        # Надсилаємо фільм
        await bot.send_video(
            chat_id=user_id,
            video=file_id,
            caption="🎬 Приємного перегляду! 🍿"
        )

        # Кнопка для перегляду фільму
        back_to_video_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Переглянути фільм",  # Текст кнопки
                        url=f"t.me/{bot.username}?start={user_id}_{file_id}"  # Посилання для переходу в бот
                    )
                ]
            ]
        )

        # Повідомлення з кнопкою
        await bot.send_message(
            chat_id=user_id,
            text="✅ Ваш фільм надіслано! Перегляньте його, натискаючи кнопку нижче:",
            reply_markup=back_to_video_keyboard
        )

        return {"success": True}

    except Exception as e:
        return {"success": False, "error": str(e)}


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

@app.post("/request-film")
async def request_film(request: Request):
    data = await request.json()
    user_id = data.get("user_id")
    film_name = data.get("film_name")

    if user_id and film_name:
        message = f"🎬 Користувач {user_id} хоче додати фільм: {film_name}"
        requests.post(
            f"https://api.telegram.org/bot{os.getenv('BOT_TOKEN')}/sendMessage",
            data={"chat_id": os.getenv("ADMIN_CHAT_ID"), "text": message}
        )

    return {"ok": True}

@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    update = types.Update(**data)
    await dp.feed_update(bot, update)
    return {"ok": True}

@app.on_event("startup")
async def startup():
    webhook_url = os.getenv("WEBHOOK_URL")
    if webhook_url:
        await bot.set_webhook(webhook_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    import uvicorn
    loop = asyncio.get_event_loop()
    loop.create_task(dp.start_polling(bot))
    uvicorn.run(app, host="0.0.0.0", port=10000)
