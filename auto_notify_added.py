import asyncio
import os
from aiogram import Bot
from google_api import get_google_service
from dotenv import load_dotenv
from datetime import datetime, timedelta
import time

messages_to_delete = []

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
SPREADSHEET_ID = os.getenv("SHEET_ID")

bot = Bot(token=BOT_TOKEN)

async def check_and_notify():
    service = get_google_service()
    sheet = service.spreadsheets()

    # Отримати запити
    reqs = sheet.values().get(
        spreadsheetId=SPREADSHEET_ID,
        range="Запити!A2:C1000"
    ).execute().get("values", [])

    # Отримати список фільмів
    films = sheet.values().get(
        spreadsheetId=SPREADSHEET_ID,
        range="Sheet1!A2:A"
    ).execute().get("values", [])
    film_names = [f[0].strip().lower() for f in films if f]

    for i, row in enumerate(reqs):  # ← БЕЗ відступу!
        if len(row) < 2:
            continue

        user_id = row[0]
        film_name = row[1]
        status = row[2] if len(row) > 2 else ""

        if status.strip().lower() != "чекає":
            print(f"⏭ Пропущено рядок {i+2} — статус був: '{status}'")
            continue

        row_number = i + 2

        try:
            msg = await bot.send_message(
                chat_id=int(user_id),
                text=f"🎬 Фільм *{film_name}* уже додано! Перевір у боті 😉",
                parse_mode="Markdown"
            )

            delete_at = datetime.utcnow() + timedelta(minutes=1)


            sheet.values().update(
                spreadsheetId=SPREADSHEET_ID,
                range=f"Запити!D{row_number}",
                valueInputOption="RAW",
                body={"values": [[delete_at.isoformat()]]}
            ).execute()

            print(f"✅ Надіслано: {film_name} → {user_id}")

            sheet.values().update(
                spreadsheetId=SPREADSHEET_ID,
                range=f"Запити!C{row_number}",
                valueInputOption="RAW",
                body={"values": [[f"✅ Надіслано {datetime.now().strftime('%d.%m %H:%M')}"]]}
            ).execute()

        except Exception as e:
            print(f"❌ Помилка надсилання для {user_id}: {e}")




async def background_deleter():
    service = get_google_service()
    sheet = service.spreadsheets()

    while True:
        now = datetime.utcnow()

        reqs = sheet.values().get(
            spreadsheetId=SPREADSHEET_ID,
            range="Запити!A2:D1000"
        ).execute().get("values", [])

        for i, row in enumerate(reqs):
            if len(row) < 4:
                continue

            user_id = row[0]
            film_name = row[1]
            delete_at_str = row[3]

            try:
                delete_at = datetime.fromisoformat(delete_at_str)
            except:
                continue

            if now >= delete_at:
                try:
                    # 🧽 Можна надсилати повідомлення про видалення, або нічого не робити
                    print(f"🗑 Видаляємо запис для {film_name} ({user_id})")

                    # Очистити колонку D
                    row_number = i + 2
                    sheet.values().update(
                        spreadsheetId=SPREADSHEET_ID,
                        range=f"Запити!D{row_number}",
                        valueInputOption="RAW",
                        body={"values": [[""]]}
                    ).execute()

                except Exception as e:
                    print(f"❗️ Помилка видалення рядка {i+2}: {e}")

        await asyncio.sleep(60)


if __name__ == "__main__":
    async def main_loop():
        asyncio.create_task(background_deleter())
        while True:
            try:
                await check_and_notify()
                print("✅ Перевірка завершена. Чекаю 5 хвилин...")
            except Exception as e:
                print(f"❌ Сталася помилка: {e}")
            await asyncio.sleep(300)

    asyncio.run(main_loop())
