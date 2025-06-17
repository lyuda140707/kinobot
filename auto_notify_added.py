import asyncio
import os
from aiogram import Bot
from google_api import get_google_service
from dotenv import load_dotenv
from datetime import datetime, timedelta
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.types import WebAppInfo




load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
SPREADSHEET_ID = os.getenv("SHEET_ID")
bot = Bot(token=BOT_TOKEN)


async def check_and_notify():
    service = get_google_service()
    sheet = service.spreadsheets()

    reqs = sheet.values().get(
        spreadsheetId=SPREADSHEET_ID,
        range="Запити!A2:C1000"
    ).execute().get("values", [])

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
            continue

        row_number = i + 2

        try:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="☕ Підтримати КіноБота", url="https://send.monobank.ua/jar/2FdmSYjoGo")],
                [InlineKeyboardButton(text="📋 Скопіювати запрошення", switch_inline_query="Дивись фільми українською — @UAKinoTochka_bot")],
              
            ])
            msg = await bot.send_message(
                chat_id=int(user_id),
                text=(
                    f"🎬 <b>{film_name}</b> уже додано! Перевір у боті 😉\n\n"
                    f"<i>Підтримай КіноБота на каву — адмінці буде дуже приємно 🫶🏻</i>\n"
                    f"<i>Натисни кнопку нижче або скопіюй посилання другу 🧡</i>\n\n"
                   
                ),
                parse_mode="HTML",
                reply_markup=keyboard,
                disable_web_page_preview=True
            )

                    
                

   
       

            delete_at = datetime.utcnow() + timedelta(hours=24)

            # Зберегти час видалення
            sheet.values().update(
                spreadsheetId=SPREADSHEET_ID,
                range=f"Запити!D{row_number}",
                valueInputOption="RAW",
                body={"values": [[delete_at.isoformat()]]}
            ).execute()

            # Зберегти message_id
            sheet.values().update(
                spreadsheetId=SPREADSHEET_ID,
                range=f"Запити!E{row_number}",
                valueInputOption="RAW",
                body={"values": [[str(msg.message_id)]]}
            ).execute()

            # Оновити статус
            sheet.values().update(
                spreadsheetId=SPREADSHEET_ID,
                range=f"Запити!C{row_number}",
                valueInputOption="RAW",
                body={"values": [[f"✅ Надіслано {datetime.now().strftime('%d.%m %H:%M')}"]]}
            ).execute()

            print(f"✅ Надіслано: {film_name} → {user_id}")

        except Exception as e:
            print(f"❌ Помилка надсилання для {user_id}: {e}")


async def background_deleter():
    service = get_google_service()
    sheet = service.spreadsheets()

    while True:
        now = datetime.utcnow()

        reqs = sheet.values().get(
            spreadsheetId=SPREADSHEET_ID,
            range="Запити!A2:E1000"
        ).execute().get("values", [])

        for i, row in enumerate(reqs):
            if len(row) < 5:
                continue

            user_id = row[0]
            film_name = row[1]
            delete_at_str = row[3]
            message_id_str = row[4]

            try:
                delete_at = datetime.fromisoformat(delete_at_str)
            except:
                continue

            if now >= delete_at:
                try:
                    await bot.delete_message(chat_id=int(user_id), message_id=int(message_id_str))
                    print(f"✅ Видалено повідомлення {message_id_str} у {user_id}")
                except Exception as e:
                    print(f"❌ Помилка видалення повідомлення {message_id_str}: {e}")

                # Очистити колонки D та E
                row_number = i + 2
                sheet.values().update(
                    spreadsheetId=SPREADSHEET_ID,
                    range=f"Запити!D{row_number}:E{row_number}",
                    valueInputOption="RAW",
                    body={"values": [["", ""]]}
                ).execute()

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
