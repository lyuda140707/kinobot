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

    for i, row in enumerate(reqs):
        if len(row) < 2:
            continue

        user_id = row[0]
        film_name = row[1]
        status = row[2] if len(row) > 2 else ""

        if status.strip().lower() != "чекає":
            print(f"⏭ Пропущено рядок {i+2} — статус був: '{status}'")
            continue

        if film_name.strip().lower() in film_names:
            row_number = i + 2
            try:
                msg = await bot.send_message(
                    chat_id=int(user_id),
                    text=f"🎬 Фільм *{film_name}* уже додано! Перевір у боті 😉",
                    parse_mode="Markdown"
                )

                print(f"✅ Надіслано: {film_name} → {user_id}")

                # Додати до черги на видалення через 24 години
                delete_at = datetime.utcnow() + timedelta(hours=24)
                messages_to_delete.append({
                    "chat_id": int(user_id),
                    "message_id": msg.message_id,
                    "delete_at": delete_at
                })
                print(f"🕓 Повідомлення заплановано на видалення: {delete_at}")

                # Оновити статус у Google Таблиці
                print(f"📝 Оновлюю статус у C{row_number} → ✅ Надіслано")
                result = sheet.values().update(
                    spreadsheetId=SPREADSHEET_ID,
                    range=f"Запити!C{row_number}",
                    valueInputOption="RAW",
                    body={"values": [[f"✅ Надіслано {datetime.now().strftime('%d.%m %H:%M')}"]]}
                ).execute()
                print("🟢 Результат оновлення статусу:", result)

            except Exception as e:
                print(f"❌ Помилка надсилання для {user_id}: {e}")

async def background_deleter():
    while True:
        now = datetime.utcnow()
        to_delete = [m for m in messages_to_delete if m["delete_at"] <= now]

        for msg in to_delete:
            try:
                await bot.delete_message(chat_id=msg["chat_id"], message_id=msg["message_id"])
                print(f"✅ Видалено повідомлення {msg['message_id']} у {msg['chat_id']}")
            except Exception as e:
                print(f"❗️ Помилка видалення {msg['message_id']}: {e}")
            messages_to_delete.remove(msg)

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
