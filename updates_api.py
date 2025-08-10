# updates_api.py
import os
from typing import Optional, Dict
from datetime import datetime
from pytz import timezone
from google_api import get_google_service

SHEET_ID = os.getenv("SHEET_ID")
SHEET_NAME = os.getenv("UPDATES_SHEET", "UPDATES")

def _now_kyiv() -> str:
    return datetime.now(timezone("Europe/Kyiv")).strftime("%Y-%m-%d %H:%M:%S")

def get_subscription(user_id: int) -> Optional[Dict]:
    """
    Повертає словник з даними підписки користувача (або None, якщо немає).
    Додає службове поле '_row' з номером рядка для оновлення.
    """
    sheet = get_google_service().spreadsheets()
    res = sheet.values().get(
        spreadsheetId=SHEET_ID,
        range=f"{SHEET_NAME}!A2:F10000"
    ).execute()
    rows = res.get("values", [])
    su = str(user_id)

    for idx, row in enumerate(rows, start=2):
        if row and row[0] == su:
            return {
                "_row": idx,
                "user_id": row[0],
                "username": row[1] if len(row) > 1 else "",
                "allow": row[2] if len(row) > 2 else "FALSE",
                "active": row[3] if len(row) > 3 else "TRUE",
                "added_at": row[4] if len(row) > 4 else "",
                "updated_at": row[5] if len(row) > 5 else "",
            }
    return None

def set_update_subscription(user_id: int,
                            username: Optional[str],
                            allow: bool,
                            *,
                            active: bool = True) -> None:
    """
    Додає або оновлює рядок у UPDATES для user_id.
    allow=True/False — згода на апдейти
    active=True/False — чи враховуємо користувача як «живого» для розсилок
    """
    sheet = get_google_service().spreadsheets()
    existing = get_subscription(user_id)
    now = _now_kyiv()
    allow_str = "TRUE" if allow else "FALSE"
    active_str = "TRUE" if active else "FALSE"

    if existing:
        # Оновлюємо рядок
        row = existing["_row"]
        body = {
            "values": [[
                str(user_id),
                username or "",
                allow_str,
                active_str,
                existing.get("added_at") or now,
                now
            ]]
        }
        sheet.values().update(
            spreadsheetId=SHEET_ID,
            range=f"{SHEET_NAME}!A{row}:F{row}",
            valueInputOption="RAW",
            body=body
        ).execute()
    else:
        # Додаємо новий
        body = {
            "values": [[
                str(user_id),
                username or "",
                allow_str,
                active_str,
                now,
                now
            ]]
        }
        sheet.values().append(
            spreadsheetId=SHEET_ID,
            range=f"{SHEET_NAME}!A:F",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body=body
        ).execute()
