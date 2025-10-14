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

def find_film_by_name(query: str):
    """Пошук фільму у Supabase (з урахуванням channel_id, message_id, file_id)"""
    import urllib.parse
    import requests

    SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
    SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_ANON")

    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        print("⚠️ SUPABASE_URL або ключ не задані — пошук через Google Sheets")
        return None

    def _sb_headers():
        return {"apikey": SUPABASE_ANON_KEY, "Authorization": f"Bearer {SUPABASE_ANON_KEY}"}

    q = urllib.parse.quote(f"*{query}*")
    url = f"{SUPABASE_URL}/rest/v1/films?select=*&title=ilike.{q}&limit=10"

    try:
        r = requests.get(url, headers=_sb_headers(), timeout=10)
        if not r.ok:
            print(f"❌ Помилка Supabase: {r.status_code} {r.text}")
            return None

        films = r.json()
        if not films:
            print("⚠️ У Supabase нічого не знайдено")
            return None

        # Якщо є кілька — беремо той, у якого є channel_id
        films_with_channel = [f for f in films if f.get("channel_id")]
        found = films_with_channel[0] if films_with_channel else films[0]
        print(f"✅ Знайдено фільм: {found.get('title')} | channel_id={found.get('channel_id')}")
        return found

    except Exception as e:
        print("❌ Помилка запиту до Supabase:", e)
        return None



def find_film_by_name(film_name):
    service = get_google_service()
    sheet = service.spreadsheets()
    SHEET_ID = os.getenv("SHEET_ID")

    # Завантажуємо всі назви з Sheet1!A2:A1000
    result = sheet.values().get(
        spreadsheetId=SHEET_ID,
        range="Sheet1!A2:A1000"
    ).execute()
    rows = result.get("values", [])

    found_row_idx = None
    for idx, row in enumerate(rows):
        if row and film_name.lower() in row[0].lower():
            found_row_idx = idx + 2  # +2 бо починаємо з другого рядка
            break

    if found_row_idx:
        film_row = sheet.values().get(
            spreadsheetId=SHEET_ID,
            range=f"Sheet1!A{found_row_idx}:L{found_row_idx}"  # до L (12 колонок)
        ).execute().get("values", [[]])[0]

        # Збираємо словник із колонок
        return {
            "Назва": film_row[0] if len(film_row) > 0 else "",
            "Тип": film_row[1] if len(film_row) > 1 else "",
            "Жанр": film_row[2] if len(film_row) > 2 else "",
            "Опис": film_row[3] if len(film_row) > 3 else "",
            "Фото": film_row[4] if len(film_row) > 4 else "",
            "message_id": film_row[5] if len(film_row)>5 else "",
            "Добірка": film_row[6] if len(film_row) > 6 else "",
            "Країна": film_row[7] if len(film_row) > 7 else "",
            "Рік": film_row[8] if len(film_row) > 8 else "",
            "file_id": film_row[9] if len(film_row) > 9 else "", 
            
            "Доступ": film_row[10] if len(film_row) > 10 else "",
            "IMDb": film_row[11] if len(film_row) > 11 else "",
        }
    return None
