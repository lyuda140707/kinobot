import asyncio
import os
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from dotenv import load_dotenv
from datetime import datetime, timedelta

from google_api import get_google_service  # твоя функція

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
SPREADSHEET_ID = os.getenv("SHEET_ID")

# ---- ⚙️ ЄДИНИЙ клієнт Google Sheets на весь процес ----
SERVICE = get_google_service()
SHEETS = SERVICE.spreadsheets()

# ---- 🤖 Єдиний екземпляр бота ----
bot = Bot(token=BOT_TOKEN)

# ---- Заготований інлайн-клавіатурний шаблон (щоб не будувати кожного разу) ----
DONATE_KB = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="☕ Підтримати RelaxTime", url="https://send.monobank.ua/jar/9wTjSL3xu2")],
    [InlineKeyboardButton(text="📋 Скопіювати запрошення", switch_inline_query="Дивись фільми українською — @Relax_TimeBot")],
])

# ================== Google Sheets helpers ==================
def is_user_blocked(user_id: int) -> bool:
    resp = SHEETS.values().get(
        spreadsheetId=SPREADSHEET_ID,
        range="Заблокували!A2:A1000"
    ).execute()
    for row in resp.get("values", []):
        if row and str(row[0]) == str(user_id):
            return True
    return False

def add_blocked_user(user_id: int):
    SHEETS.values().append(
        spreadsheetId=SPREADSHEET_ID,
        range="Заблокували!A2",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": [[str(user_id)]]}
    ).execute()

def remove_user_from_blocklist(user_id: int):
    resp = SHEETS.values().get(
        spreadsheetId=SPREADSHEET_ID,
        range="Заблокували!A2:A1000"
    ).execute()
    new_values = [row for row in resp.get("values", []) if row and str(row[0]) != str(user_id)]
    # перезаписуємо діапазон
    SHEETS.values().update(
        spreadsheetId=SPREADSHEET_ID,
        range="Заблокували!A2:A1000",
        valueInputOption="RAW",
        body={"values": new_values or [[""]]}  # не залишаємо повністю порожнім
    ).execute()

# ================== Telegram helpers ==================
async def safe_send(user_id: int, text: str, **kwargs):
    try:
        return await bot.send_message(chat_id=user_id, text=text, **kwargs)
    except TelegramForbiddenError:
        # користувач заблокував — занесемо в таблицю один раз
        add_blocked_user(user_id)
        print(f"❌ Користувач {user_id} заблокував бота (додано до 'Заблокували').")
    except TelegramBadRequest as e:
        print(f"❌ BadRequest {user_id}: {e}")
    except Exception as e:
        print(f"❌ Інша помилка {user_id}: {e}")
    return None

# ================== Основна логіка ==================
async def check_and_notify():
    # Мінімальні діапазони, жодних лишніх колонок
    reqs = SHEETS.values().get(
        spreadsheetId=SPREADSHEET_ID,
        range="Запити!A2:G1000"
    ).execute().get("values", [])

    # ⚠️ film_names був зайвим і споживав памʼять — прибрав

    for i, row in enumerate(reqs):
        if len(row) < 2:
            continue

        user_id_raw = row[0]
        film_name = row[1]
        status = row[2].strip().lower() if len(row) > 2 and row[2] else ""
        help_text = row[6].strip() if len(row) > 6 and row[6] else ""
        if status != "чекає":
            continue

        try:
            user_id = int(user_id_raw)
        except:
            continue

        if is_user_blocked(user_id):
            # не шлемо, не будуємо зайвих об'єктів
            continue

        row_number = i + 2

        text_parts = [
            f"🎬 <b>{film_name}</b> уже додано! Перевір у боті 😉",
        ]
        if help_text:
            text_parts.append(help_text)
        text_parts += [
            "",
            "<i>Адмінка старалась для вас 🎬✨</i>",
            "<i>Хочеш подякувати — пригости кавою ☕😉</i>",
        ]
        text = "\n".join(text_parts)

        sent = await safe_send(
            user_id,
            text,
            parse_mode="HTML",
            reply_markup=DONATE_KB,
            disable_web_page_preview=True
        )
        if not sent:
            continue

        # якщо дійшло — зняти з «Заблокували», якщо раніше туди потрапляв
        if is_user_blocked(user_id):
            remove_user_from_blocklist(user_id)

        delete_at = datetime.utcnow() + timedelta(hours=24)

        # мінімальна кількість update-запитів
        SHEETS.values().batchUpdate(
            spreadsheetId=SPREADSHEET_ID,
            body={
                "valueInputOption": "RAW",
                "data": [
                    {"range": f"Запити!D{row_number}", "values": [[delete_at.isoformat()]]},
                    {"range": f"Запити!E{row_number}", "values": [[str(sent.message_id)]]},
                    {"range": f"Запити!C{row_number}", "values": [[f"✅ Надіслано {datetime.now().strftime('%d.%m %H:%M')}"]]},
                ]
            }
        ).execute()

        print(f"✅ Надіслано: {film_name} → {user_id}")

async def background_deleter():
    print("🚀 Фоновий процес видалення запущено!")
    while True:
        now = datetime.utcnow()
        reqs = SHEETS.values().get(
            spreadsheetId=SPREADSHEET_ID,
            range="Запити!A2:E1000"
        ).execute().get("values", [])

        for i, row in enumerate(reqs):
            if len(row) < 5:
                continue
            user_id_raw, _, _, delete_at_str, message_id_str = row[:5]

            if not delete_at_str:
                continue
            try:
                user_id = int(user_id_raw)
                message_id = int(message_id_str)
                delete_at = datetime.fromisoformat(delete_at_str)
            except Exception:
                continue

            if now >= delete_at:
                try:
                    await bot.delete_message(chat_id=user_id, message_id=message_id)
                    print(f"✅ Видалено повідомлення {message_id} у {user_id}")
                except Exception as e:
                    print(f"❌ Помилка видалення {message_id} для {user_id}: {e}")

                row_number = i + 2
                SHEETS.values().update(
                    spreadsheetId=SPREADSHEET_ID,
                    range=f"Запити!D{row_number}:E{row_number}",
                    valueInputOption="RAW",
                    body={"values": [["", ""]]}
                ).execute()

        await asyncio.sleep(60)

# ================== Точка входу ==================
async def main():
    # один background task
    deleter_task = asyncio.create_task(background_deleter())
    try:
        while True:
            try:
                await check_and_notify()
            except Exception as e:
                print(f"❌ Сталася помилка: {e}")
            await asyncio.sleep(300)
    finally:
        # акуратно закриваємо HTTP-сесію бота
        await bot.session.close()
        deleter_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await deleter_task

if __name__ == "__main__":
    import contextlib
    asyncio.run(main())
