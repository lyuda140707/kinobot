import gspread
import os
import json
from oauth2client.service_account import ServiceAccountCredentials
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build


def get_gsheet_data():
    creds_json = os.getenv("GOOGLE_SHEETS_CREDENTIALS_JSON")
    creds_dict = json.loads(creds_json)

    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)

    sheet_id = os.getenv("SHEET_ID")
    sheet = client.open_by_key(sheet_id).sheet1
    return sheet.get_all_records()

def get_google_service():
    creds_dict = json.loads(os.getenv("GOOGLE_SHEETS_CREDENTIALS_JSON"))
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)

    service = build("sheets", "v4", credentials=creds)
    return service

from datetime import datetime
from pytz import timezone
from google_api import get_google_service
import os

def add_user_if_not_exists(user_id: int, username: str, first_name: str):
    service = get_google_service()
    sheet = service.spreadsheets()
    SHEET_ID = os.getenv("SHEET_ID")

    # Отримати існуючі user_id
    result = sheet.values().get(
        spreadsheetId=SHEET_ID,
        range="Користувачі!A2:A1000"
    ).execute()
    existing_ids = [row[0] for row in result.get("values", []) if row]

    if str(user_id) in existing_ids:
        return  # Користувач уже є

    # Додаємо нового
    kyiv = timezone("Europe/Kyiv")
    now = datetime.now(kyiv).strftime("%Y-%m-%d %H:%M:%S")

    sheet.values().append(
        spreadsheetId=SHEET_ID,
        range="Користувачі!A2:D2",
        valueInputOption="USER_ENTERED",
        body={"values": [[str(user_id), username or "", first_name or "", now]]}
    ).execute()
