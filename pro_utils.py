import os
import json
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from datetime import datetime, timedelta

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")


# ✅ Додати користувача в PRO
def add_pro_user(user_id):
    creds = Credentials.from_service_account_info(
        json.loads(os.getenv("GOOGLE_SHEETS_CREDENTIALS_JSON")), scopes=SCOPES
    )
    service = build("sheets", "v4", credentials=creds)
    sheet = service.spreadsheets()

    today = datetime.utcnow().strftime("%Y-%m-%d")
    values = [[str(user_id), today]]
    sheet.values().append(
        spreadsheetId=SPREADSHEET_ID,
        range="PRO_Users!A:B",
        valueInputOption="USER_ENTERED",
        body={"values": values},
    ).execute()


# ✅ Перевірити чи активний PRO
def is_pro_active(user_id):
    creds = Credentials.from_service_account_info(
        json.loads(os.getenv("GOOGLE_SHEETS_CREDENTIALS_JSON")), scopes=SCOPES
    )
    service = build("sheets", "v4", credentials=creds)
    sheet = service.spreadsheets()

    resp = sheet.values().get(
        spreadsheetId=SPREADSHEET_ID, range="PRO_Users!A:B"
    ).execute()

    rows = resp.get("values", [])[1:]  # Пропускаємо заголовки
    for row in rows:
        if str(user_id) == row[0]:
            date = datetime.strptime(row[1], "%Y-%m-%d")
            if datetime.utcnow() - date < timedelta(days=30):
                return True
    return False
