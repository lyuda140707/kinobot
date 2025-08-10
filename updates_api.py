# updates_api.py
import os
from datetime import datetime
from google_api import get_google_service

SHEET_ID = os.getenv("SHEET_ID")

def set_update_subscription(user_id: int, username: str, allow: bool):
    service = get_google_service()
    sheet = service.spreadsheets()
    rng = "UPDATES!A2:E100000"
    res = sheet.values().get(spreadsheetId=SHEET_ID, range=rng).execute()
    rows = res.get("values", [])

    uid = str(user_id)
    row_index = None
    for i, r in enumerate(rows):
        if len(r) >= 1 and r[0] == uid:
            row_index = i
            break

    values = [
        uid,
        username or "",
        "TRUE" if allow else "FALSE",
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "TRUE"  # active
    ]

    if row_index is None:
        sheet.values().append(
            spreadsheetId=SHEET_ID,
            range="UPDATES!A2",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values":[values]}
        ).execute()
    else:
        row_num = row_index + 2
        sheet.values().update(
            spreadsheetId=SHEET_ID,
            range=f"UPDATES!A{row_num}:E{row_num}",
            valueInputOption="USER_ENTERED",
            body={"values":[values]}
        ).execute()

def get_active_subscribers():
    service = get_google_service()
    sheet = service.spreadsheets()
    res = sheet.values().get(
        spreadsheetId=SHEET_ID,
        range="UPDATES!A2:E100000"
    ).execute()
    rows = res.get("values", [])
    out = []
    for r in rows:
        if len(r) >= 5:
            allow = r[2].strip().upper() == "TRUE"
            active = r[4].strip().upper() == "TRUE"
            if allow and active and r[0].isdigit():
                out.append(int(r[0]))
    return out

def set_inactive(user_id: int):
    service = get_google_service()
    sheet = service.spreadsheets()
    res = sheet.values().get(
        spreadsheetId=SHEET_ID,
        range="UPDATES!A2:E100000"
    ).execute()
    rows = res.get("values", [])

    uid = str(user_id)
    for i, r in enumerate(rows):
        if len(r) >= 1 and r[0] == uid:
            row_num = i + 2
            sheet.values().update(
                spreadsheetId=SHEET_ID,
                range=f"UPDATES!E{row_num}",
                valueInputOption="USER_ENTERED",
                body={"values":[["FALSE"]]}
            ).execute()
            break
