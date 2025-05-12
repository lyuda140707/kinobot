from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from google_api import get_gsheet_data
import os
from dotenv import load_dotenv
load_dotenv()
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram import F
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import asyncio
logging.basicConfig(level=logging.INFO)

app = FastAPI()


bot = Bot(
    token=os.getenv("BOT_TOKEN"),
    default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
)
dp = Dispatcher(storage=MemoryStorage())

webapp_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(
        text="🎬 Відкрити кіно-застосунок",
        web_app=WebAppInfo(url="https://lyuda140707.github.io/kinobot-webapp/")
    )]
])


@dp.message(Command("webapp"))
async def send_webapp(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🎬 Відкрити WebApp",
            web_app=WebAppInfo(url="https://lyuda140707.github.io/kinobot-webapp/")
        )]
    ])
    await message.answer("Ось кнопка для відкриття WebApp:", reply_markup=keyboard)


@dp.message(Command("start"))
async def start_handler(message: types.Message):
    if message.text and len(message.text.split()) > 1:
        query = message.text.split(maxsplit=1)[1]
    else:
        query = None

    if query:
        print(f"🔍 Отримано запит: {query}")
        films = get_gsheet_data()
        for film in films:
            if query.lower() in film.get("Назва", "").lower() or query.lower() in film.get("Опис", "").lower():
                name = film["Назва"]
                desc = film["Опис"]
                file_id = film.get("file_id")
                caption = f"*🎬 {name}*\n{desc}"

                print(f"✅ Надсилаємо фільм: {name}")
                print(f"🎞 file_id: {file_id}")

                if file_id:
                    await message.answer_video(file_id, caption=caption, parse_mode="Markdown")
                else:
                    await message.answer(caption, parse_mode="Markdown")
                return
        await message.answer("Фільм не знайдено 😢")
    else:
        await message.answer(
            "Привіт! Натисни кнопку нижче, щоб відкрити кіно-застосунок:",
            reply_markup=webapp_keyboard
        )

@dp.message(F.video)
async def get_file_id(message: types.Message):
    file_id = message.video.file_id
    await message.answer(f"🎥 file_id:\n<code>{file_id}</code>", parse_mode="HTML")

@dp.message(F.text)
async def search_film(message: types.Message):
    if not message.text:
        return

    query = message.text.lower()
    films = get_gsheet_data()

    for film in films:
        if query in film["Назва"].lower():
            name = film.get("Назва", "Без назви")
            desc = film.get("Опис", "Без опису")
            file_id = film.get("file_id")

            caption = f"*🎬 {name}*\n{desc}"
            print(f"✅ Надсилаємо фільм: {name}")
            print(f"🎞 file_id: {file_id}")

            if file_id:
                await message.answer_video(file_id, caption=caption, parse_mode="Markdown")
            else:
                await message.answer(caption, parse_mode="Markdown")
            return

    await message.answer("Фільм не знайдено 😢")

@app.post("/send-video")
async def send_video(request: Request):
    data = await request.json()
    user_id = data.get("user_id")
    file_id = data.get("file_id")

    if not user_id or not file_id:
        return JSONResponse(content={"success": False, "error": "Missing user_id or file_id"}, status_code=400)

    try:
        await bot.send_video(chat_id=user_id, video=file_id, parse_mode="Markdown")
        return {"success": True}
    except Exception as e:
        print(f"Помилка надсилання відео: {e}")
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=500)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    import uvicorn
    loop = asyncio.get_event_loop()
    loop.create_task(main())
    uvicorn.run(app, host="0.0.0.0", port=10000)



