import os
import json
import time
from datetime import datetime
from pytz import timezone
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.service_account import Credentials


def get_google_service():
    creds_dict = json.loads(os.getenv("GOOGLE_SHEETS_CREDENTIALS_JSON"))
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    service = build("sheets", "v4", credentials=creds)
    return service


def safe_get_sheet_data(service, spreadsheet_id, range_, retries=3, delay=2):
    for attempt in range(retries):
        try:
            result = service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=range_
            ).execute()
            return result.get("values", [])
        except HttpError as e:
            if e.resp.status in [500, 429] and attempt < retries - 1:
                print(f"⚠️ Спроба {attempt+1} — помилка {e.resp.status}, повтор через {delay}с")
                time.sleep(delay)
                delay *= 2
            else:
                print("❌ Помилка Google Sheets:", e)
                raise


def safe_append_to_sheet(service, spreadsheet_id, range_, values, retries=3, delay=2):
    for attempt in range(retries):
        try:
            result = service.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id,
                range=range_,
                valueInputOption="USER_ENTERED",
                body={"values": values}
            ).execute()
            return result
        except HttpError as e:
            if e.resp.status in [500, 429] and attempt < retries - 1:
                print(f"⚠️ Append-спроба {attempt+1} — помилка {e.resp.status}, повтор через {delay}с")
                time.sleep(delay)
                delay *= 2
            else:
                print("❌ Append помилка Google Sheets:", e)
                raise


def add_user_if_not_exists(user_id: int, username: str, first_name: str):
    service = get_google_service()
    SHEET_ID = os.getenv("SHEET_ID")

    existing_ids_data = safe_get_sheet_data(service, SHEET_ID, "Користувачі!A2:A1000")
    existing_ids = [row[0] for row in existing_ids_data if row]

    if str(user_id) in existing_ids:
        return

    kyiv = timezone("Europe/Kyiv")
    now = datetime.now(kyiv).strftime("%Y-%m-%d %H:%M:%S")

    safe_append_to_sheet(
        service,
        spreadsheet_id=SHEET_ID,
        range_="Користувачі!A2:D2",
        values=[[str(user_id), username or "", first_name or "", now]]
    )

def get_gsheet_data(sheet_range):
    service = get_google_service()
    SHEET_ID = os.getenv("SHEET_ID")
    return safe_get_sheet_data(service, SHEET_ID, sheet_range)

