import asyncio
import os
from aiogram import Bot
from google_api import get_google_service
from dotenv import load_dotenv
from datetime import datetime, timedelta
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.types import WebAppInfo




load_dotenv()
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

def is_user_blocked(user_id: int, service, spreadsheet_id: str) -> bool:
    sheet = service.spreadsheets()
    response = sheet.values().get(
        spreadsheetId=spreadsheet_id,
        range="Заблокували!A2:A1000"
    ).execute()
    blocked_ids = [str(row[0]) for row in response.get("values", []) if row]
    return str(user_id) in blocked_ids

def add_blocked_user(user_id: int, service, spreadsheet_id: str):
    sheet = service.spreadsheets()
    sheet.values().append(
        spreadsheetId=spreadsheet_id,
        range="Заблокували!A2",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": [[str(user_id)]]}
    ).execute()

def remove_user_from_blocklist(user_id: int, service, spreadsheet_id: str):
    sheet = service.spreadsheets()
    response = sheet.values().get(
        spreadsheetId=spreadsheet_id,
        range="Заблокували!A2:A1000"
    ).execute()

    values = response.get("values", [])
    new_values = []

    for row in values:
        if row and str(row[0]) != str(user_id):
            new_values.append(row)

    # Повністю перезаписати список, без видаленого user_id
    sheet.values().update(
        spreadsheetId=spreadsheet_id,
        range="Заблокували!A2:A1000",
        valueInputOption="RAW",
        body={"values": new_values}
    ).execute()


async def safe_send(bot: Bot, user_id: int, text: str, service=None, spreadsheet_id=None, **kwargs):
    try:
        sent_msg = await bot.send_message(chat_id=user_id, text=text, **kwargs)
        return sent_msg
    except TelegramForbiddenError:
        print(f"❌ Користувач {user_id} заблокував бота")
        if service and spreadsheet_id:
            print(f"⚠️ Додаємо користувача {user_id} у таблицю Заблокували")
            add_blocked_user(user_id, service, spreadsheet_id)
    except TelegramBadRequest as e:
        print(f"❌ BadRequest {user_id}: {e}")
    except Exception as e:
        print(f"❌ Інша помилка {user_id}: {e}")
    return False


BOT_TOKEN = os.getenv("BOT_TOKEN")
SPREADSHEET_ID = os.getenv("SHEET_ID")
bot = Bot(token=BOT_TOKEN)


async def check_and_notify():
    service = get_google_service()
    sheet = service.spreadsheets()

    reqs = sheet.values().get(
        spreadsheetId=SPREADSHEET_ID,
        range="Запити!A2:G1000"
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
        help_text = row[6] if len(row) > 6 else ""
        print(f"ℹ️ user_id: {user_id}, help_text: '{help_text}'")
         

        if status.strip().lower() != "чекає":
            continue
        if is_user_blocked(user_id, service, SPREADSHEET_ID):
            print(f"⛔ Пропускаємо {user_id} — користувач заблокував бота")
            continue

        
            


        row_number = i + 2

        try:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="☕ Підтримати RelaxTime", url="https://send.monobank.ua/jar/2FdmSYjoGo")],
                [InlineKeyboardButton(text="📋 Скопіювати запрошення", switch_inline_query="Дивись фільми українською — @Relax_TimeBot")],
              
            ])
            
            text = (
                f"🎬 <b>{film_name}</b> уже додано! Перевір у боті 😉\n\n"
            )
            if help_text.strip():
                text += f"{help_text.strip()}\n\n"

            text += (
                "<i>Підтримай RelaxTime на каву — адмінці буде дуже приємно 🫶🏻</i>\n"
                "<i>Натисни кнопку нижче або скопіюй посилання другу 🧡</i>\n\n"
            )

            sent_msg = await safe_send(
                bot,
                int(user_id),
                text,
                service=service,  # ← ДОДАЙ ЦЕ
                spreadsheet_id=SPREADSHEET_ID,  # ← І ЦЕ
                parse_mode="HTML",
                reply_markup=keyboard,
                disable_web_page_preview=True
            )
                

            if not sent_msg:
                continue
                
            if is_user_blocked(user_id, service, SPREADSHEET_ID):
                print(f"🔓 {user_id} розблокував бота — видаляємо з таблиці Заблокували")
                remove_user_from_blocklist(user_id, service, SPREADSHEET_ID)

           

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
                body={"values": [[str(sent_msg.message_id)]]}
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
    print("🚀 Фоновий процес видалення запущено!")

    while True:
        now = datetime.utcnow()
        print(f"🔍 Перевірка на видалення повідомлень {now.isoformat()}")

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

            if not delete_at_str.strip():
                continue

            try:
                delete_at = datetime.fromisoformat(delete_at_str)
            except Exception as e:
                print(f"⚠️ Некоректна дата у рядку {i + 2}: {delete_at_str} — {e}")
                continue

            if now >= delete_at:
                try:
                    await bot.delete_message(chat_id=int(user_id), message_id=int(message_id_str))
                    print(f"✅ Видалено повідомлення {message_id_str} у {user_id}")
                except Exception as e:
                    print(f"❌ Помилка видалення повідомлення {message_id_str} для {user_id}: {e}")

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
