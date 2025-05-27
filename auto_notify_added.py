import asyncio
import os
from aiogram import Bot
from google_api import get_google_service  # у тебе вже є
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
SPREADSHEET_ID = os.getenv("SHEET_ID")

bot = Bot(token=BOT_TOKEN)

async def check_and_notify():
    service = get_google_service()
    sheet = service.spreadsheets()

    # 1. Отримати запити
    reqs = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range="Запити!A2:B").execute().get("values", [])
    # 2. Отримати список назв фільмів
    films = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range="Sheet1!A2:A").execute().get("values", [])
    film_names = [f[0].strip().lower() for f in films if f]

    rows_to_delete = []

    for i, row in enumerate(reqs):
        if len(row) < 2:
            continue
        user_id, film_name = row[0], row[1]
        if film_name.strip().lower() in film_names:
            try:
                await bot.send_message(
                    chat_id=int(user_id),
                    text=f"🎬 Фільм *{film_name}* уже додано! Перевір у боті 😉",
                    parse_mode="Markdown"
                )
                print(f"✅ Надіслано: {film_name} → {user_id}")
                rows_to_delete.append(i + 2)
            except Exception as e:
                print(f"❌ Помилка надсилання для {user_id}: {e}")

    # 3. Очистити оброблені запити
    for row in reversed(rows_to_delete):
        sheet.values().clear(spreadsheetId=SPREADSHEET_ID, range=f"Запити!A{row}:B{row}").execute()

if __name__ == "__main__":
    asyncio.run(check_and_notify())
