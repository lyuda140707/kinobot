import asyncio
import os
from aiogram import Bot
from google_api import get_google_service
from dotenv import load_dotenv
from datetime import datetime
import time

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
        range="Запити!A2:C1000"  # З запасом, щоб точно зчитати C
    ).execute().get("values", [])

    # Отримати список фільмів
    films = sheet.values().get(
        spreadsheetId=SPREADSHEET_ID,
        range="Sheet1!A2:A"
    ).execute().get("values", [])
    film_names = [f[0].strip().lower() for f in films if f]

    for i, row in enumerate(reqs):
        # Мінімум 2 стовпці: user_id і film_name
        if len(row) < 2:
            continue

        user_id = row[0]
        film_name = row[1]
        status = row[2] if len(row) > 2 else ""

        # Лише якщо статус == "чекає"
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

                # Зачекати 60 сек і видалити
                await asyncio.sleep(60)
                try:
                    await bot.delete_message(chat_id=int(user_id), message_id=msg.message_id)
                except Exception as e:
                    print(f"⚠️ Не вдалося видалити повідомлення: {e}")

                # Оновити статус
                print(f"📝 Оновлюю статус у C{row_number} → ✅ Надіслано")
                sheet.values().update(
                    spreadsheetId=SPREADSHEET_ID,
                    range=f"Запити!C{row_number}",
                    valueInputOption="RAW",
                    body={"values": [[f"✅ Надіслано {datetime.now().strftime('%d.%m %H:%M')}"]]}
                ).execute()

            except Exception as e:
                print(f"❌ Помилка надсилання для {user_id}: {e}")

if __name__ == "__main__":
    while True:
        try:
            asyncio.run(check_and_notify())
            print("✅ Перевірка завершена. Чекаю 5 хвилин...")
        except Exception as e:
            print(f"❌ Сталася помилка: {e}")
        time.sleep(300)
