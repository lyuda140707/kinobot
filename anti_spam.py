# anti_spam.py
from google_api import get_google_service
from datetime import datetime, timedelta
from pytz import timezone
import os

SHEET_ID = os.getenv("SHEET_ID")


def get_row_by_user(sheet, user_id):
    data = sheet.values().get(
        spreadsheetId=SHEET_ID,
        range="АнтиСпам!A2:D2000"
    ).execute().get("values", [])

    for idx, row in enumerate(data, start=2):
        if row and row[0] == str(user_id):
            return idx, row
    return None, None


def update_row(sheet, row_number, values):
    sheet.values().update(
        spreadsheetId=SHEET_ID,
        range=f"АнтиСпам!A{row_number}:D{row_number}",
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

    # якщо юзера ще нема
    if not row:
        append_row(sheet, [str(user_id), now.isoformat(), "1", ""])
        return True, None

    last_time = datetime.fromisoformat(row[1])
    counter = int(row[2])
    banned_until = row[3]

    # Перевірка бана
    if banned_until:
        banned_dt = datetime.fromisoformat(banned_until)
        if now < banned_dt:
            return False, banned_dt

    # обнулення якщо пройшло більше 3 хв
    if (now - last_time).seconds > 180:
        update_row(sheet, row_number, [str(user_id), now.isoformat(), "1", ""])
        return True, None

    # якщо менше 3 хв — це потік завантаження
    counter += 1

    # Ліміт — 3 запити за 3 хв → бан на 1 годину
    if counter >= 3:
        banned_until_dt = now + timedelta(hours=1)
        update_row(sheet, row_number, [
            str(user_id),
            now.isoformat(),
            str(counter),
            banned_until_dt.isoformat()
        ])
        return False, banned_until_dt

    # якщо менше ліміту — оновити
    update_row(sheet, row_number, [
        str(user_id),
        now.isoformat(),
        str(counter),
        ""
    ])
    return True, None
