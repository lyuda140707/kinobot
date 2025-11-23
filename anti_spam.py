from google_api import get_google_service
from datetime import datetime, timedelta
from pytz import timezone
import os

SHEET_ID = os.getenv("SHEET_ID")


def get_row_by_user(sheet, user_id):
    data = sheet.values().get(
        spreadsheetId=SHEET_ID,
        range="АнтиСпам!A2:E2000"
    ).execute().get("values", [])

    for idx, row in enumerate(data, start=2):
        if row and row[0] == str(user_id):
            return idx, row
    return None, None


def update_row(sheet, row_number, values):
    sheet.values().update(
        spreadsheetId=SHEET_ID,
        range=f"АнтиСпам!A{row_number}:E{row_number}",
        valueInputOption="RAW",
        body={"values": [values]}
    ).execute()


def append_row(sheet, values):
    sheet.values().append(
        spreadsheetId=SHEET_ID,
        range="АнтиСпам!A2",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": [values]}
    ).execute()


def check_limit(user_id: int, is_pro: bool):
    if is_pro:
        return True, None  # PRO — без обмежень

    service = get_google_service()
    sheet = service.spreadsheets()

    kyiv = timezone("Europe/Kyiv")
    now = datetime.now(kyiv)

    row_number, row = get_row_by_user(sheet, user_id)

    # Якщо юзера ще нема → створюємо рядок
    if not row:
        append_row(sheet, [
            str(user_id),
            now.isoformat(),
            "1",
            "",
            "0"    # ban_count
        ])
        return True, None

    # --- Автопідстраховка ---
    last_request = row[1] if len(row) > 1 and row[1] else None
    counter = int(row[2]) if len(row) > 2 and row[2] else 0
    banned_until = row[3] if len(row) > 3 and row[3] else None
    ban_count = int(row[4]) if len(row) > 4 and row[4] else 0
    # ---------------------------

    last_time = datetime.fromisoformat(last_request) if last_request else None

    # 🔒 Перевірка активного бана
    if banned_until:
        banned_dt = datetime.fromisoformat(banned_until)
        if now < banned_dt:
            return False, banned_dt

    # 🕒 Якщо минуло більше 180 секунд → скидаємо лічильник
    if last_time is None or (now - last_time).total_seconds() > 180:
        update_row(sheet, row_number, [
            str(user_id),
            now.isoformat(),
            "1",
            "",
            str(ban_count)
        ])
        return True, None

    # 🚨 Якщо менше 3 хвилин → це серія запитів
    counter += 1

    # ⚠️ Ліміт перевищено: 3 запити за <3 хвилин → БАН
    if counter >= 3:

        ban_count += 1  # збільшуємо кількість банів

        # ВАРІАНТ A — тривалості бану
        if ban_count == 1:
            ban_duration = timedelta(hours=1)
        elif ban_count == 2:
            ban_duration = timedelta(hours=3)
        else:
            ban_duration = timedelta(hours=24)

        banned_until_dt = now + ban_duration

        update_row(sheet, row_number, [
            str(user_id),
            now.isoformat(),
            str(counter),
            banned_until_dt.isoformat(),
            str(ban_count)
        ])

        # 🔔 Повідомлення адміну
        from bot import safe_send_admin, bot as tg_bot
        ADMIN_ID = os.getenv("ADMIN_ID")

        try:
            import asyncio
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[[
                    InlineKeyboardButton(
                        text=f"🔓 Розблокувати {user_id}",
                        callback_data=f"unban:{user_id}"
                    )
                ]]
            )

            asyncio.create_task(safe_send_admin(
                tg_bot,
                ADMIN_ID,
                f"🚫 Користувача {user_id} заблоковано.\n"
                f"🔢 Номер бана: {ban_count}\n"
                f"🕒 Тривалість: {ban_duration}\n"
                f"До: {banned_until_dt.strftime('%H:%M %d.%m')}",
                reply_markup=keyboard
            ))
        except Exception as e:
            print("Помилка надсилання лога адміну:", e)

        return False, banned_until_dt

    # ✅ Якщо не перевищив ліміт — просто оновити рядок
    update_row(sheet, row_number, [
        str(user_id),
        now.isoformat(),
        str(counter),
        "",
        str(ban_count)
    ])

    return True, None
