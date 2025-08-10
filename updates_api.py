# updates_api.py
import os
from datetime import datetime
from typing import List, Optional
from pytz import timezone
from google_api import get_google_service

SHEET_ID = os.getenv("SHEET_ID")
SHEET_NAME = os.getenv("UPDATES_SHEET", "UPDATES")

def _now_kyiv() -> str:
    return datetime.now(timezone("Europe/Kyiv")).strftime("%Y-%m-%d %H:%M:%S")

def set_update_subscription(user_id: int,
                            username: Optional[str],
                            allow: bool,
                            *,
                            active: bool = True) -> None:
    """
    Додає/оновлює рядок у UPDATES для user_id.
    allow=True/False — згода на апдейти
    active=True/False — чи вважаємо користувача «живим» для розсилок
    """
    service = get_google_service().spreadsheets()

    # зчитати існуючі рядки
    res = service.values().get(
        spreadsheetId=SHEET_ID,
        range=f"{SHEET_NAME}!A2:E1000"
    ).execute()
    rows = res.get("values", [])

    # пошук рядка користувача
    row_num = None
    for i, row in enumerate(rows, start=2):
        if len(row) >= 1 and row[0].strip() == str(user_id):
            row_num = i
            break

    values = [[
        str(user_id),
        (username or ""),
        "TRUE" if allow else "FALSE",
        _now_kyiv(),
        "TRUE" if active else "FALSE",
    ]]

    if row_num:  # оновити існуючий
        service.values().update(
            spreadsheetId=SHEET_ID,
            range=f"{SHEET_NAME}!A{row_num}:E{row_num}",
            valueInputOption="USER_ENTERED",
            body={"values": values}
        ).execute()
    else:       # додати новий
        service.values().append(
            spreadsheetId=SHEET_ID,
            range=f"{SHEET_NAME}!A2",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values": values}
        ).execute()


def get_active_subscribers() -> List[int]:
    """Повертає user_id усіх, хто allow_updates=TRUE і active=TRUE."""
    service = get_google_service().spreadsheets()
    res = service.values().get(
        spreadsheetId=SHEET_ID,
        range=f"{SHEET_NAME}!A2:E1000"
    ).execute()
    rows = res.get("values", [])

    uids: List[int] = []
    for row in rows:
        if len(row) < 5:
            continue
        uid, _, allow, _, active = (row + ["", "", "", "", ""])[:5]
        if allow.strip().upper() == "TRUE" and active.strip().upper() == "TRUE":
            try:
                uids.append(int(uid))
            except:
                pass
    return uids


def set_inactive(user_id: int) -> None:
    """Позначає користувача як inactive=FALSE і оновлює updated_at."""
    service = get_google_service().spreadsheets()
    res = service.values().get(
        spreadsheetId=SHEET_ID,
        range=f"{SHEET_NAME}!A2:E1000"
    ).execute()
    rows = res.get("values", [])

    for i, row in enumerate(rows, start=2):
        if len(row) >= 1 and row[0].strip() == str(user_id):
            service.values().update(
                spreadsheetId=SHEET_ID,
                range=f"{SHEET_NAME}!C{i}:E{i}",
                valueInputOption="USER_ENTERED",
                body={"values": [[row[2] if len(row) > 2 else "FALSE", _now_kyiv(), "FALSE"]]}
            ).execute()
            return
