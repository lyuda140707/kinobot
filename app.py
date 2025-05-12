from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from aiogram import types
from bot import dp, bot
import os
import asyncio
import requests
import logging

# Налаштовуємо логування
logging.basicConfig(level=logging.INFO)

app = FastAPI()

@app.post("/send-video")
async def send_video(request: Request):
    data = await request.json()
    user_id = data.get("user_id")
    file_id = data.get("file_id")

    if not user_id or not file_id:
        return {"success": False, "error": "user_id або file_id відсутні"}

    try:
        # Вручну вказуємо username бота
        bot_username = "UAKinoTochka_bot"  # Введіть ваш реальний username

        # Надсилаємо фільм
        message = await bot.send_video(
            chat_id=user_id,
            video=file_id,
            caption="🎬 Приємного перегляду! 🍿"
        )

        logging.info(f"Відео надіслано користувачу {user_id} з file_id {file_id}")

        # Кнопка для переходу в Telegram з WebApp
        back_to_video_webapp_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Переглянути фільм",  # Текст кнопки
                        url=f"t.me/{bot_username}?start={user_id}_{file_id}"  # Посилання для переходу в Telegram
                    )
                ]
            ]
        )

        # Повідомлення для WebApp з кнопкою для переходу в Telegram
        await bot.send_message(
            chat_id=user_id,
            text="✨ Фільм надіслано вам у Telegram! Натисніть нижче, щоб переглянути фільм:",
            reply_markup=back_to_video_webapp_keyboard
        )

        return {"success": True}

    except Exception as e:
        logging.error(f"Помилка при відправці відео: {str(e)}")
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
    try:
        # Отримуємо дані з webhook
        data = await request.json()

        # Логування отриманих даних
        logging.info(f"Отримані дані з webhook: {data}")

        # Перевірка, чи є необхідні поля в даних
        if not data.get("update_id") or not data.get("message"):
            logging.error("Немає необхідних даних в оновленні")
            return {"success": False, "error": "Невірний формат даних"}

        # Створюємо оновлення з отриманих даних
        update = types.Update(**data)

        # Відправляємо в dispatcher для обробки
        await dp.feed_update(bot, update)
        return {"ok": True}

    except Exception as e:
        logging.error(f"Помилка при обробці webhook: {str(e)}")
        return {"success": False, "error": str(e)}

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
