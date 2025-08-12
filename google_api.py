import gspread
import os
import json
from oauth2client.service_account import ServiceAccountCredentials
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import time, random, socket
import httplib2
from googleapiclient.errors import HttpError

def get_gsheet_data():
    creds_json = os.getenv("GOOGLE_SHEETS_CREDENTIALS_JSON")
    creds_dict = json.loads(creds_json)

    scope = [
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/drive.readonly"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)

    sheet_id = os.getenv("SHEET_ID")
    sheet = client.open_by_key(sheet_id).sheet1
    return sheet.get_all_records()

def get_google_service():
    creds_dict = json.loads(os.getenv("GOOGLE_SHEETS_CREDENTIALS_JSON"))
    scopes = ["https://www.googleapis.com/auth/spreadsheets",
              "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)

    # Важливо: таймаут на мережу
    http = httplib2.Http(timeout=15)

    # Важливо: cache_discovery=False прибирає warning про file_cache
    service = build("sheets", "v4", credentials=creds, http=http, cache_discovery=False)
    return service

def _exec_with_retry(request, tries=5):
    """
    Виконує запит до Sheets із ретраями на 500/502/503/504/429 та таймаути.
    """
    for i in range(tries):
        try:
            # num_retries=0 — керуємо ретраями самі
            return request.execute(num_retries=0)
        except HttpError as e:
            status = getattr(e, "resp", None) and e.resp.status
            if status in (500, 502, 503, 504, 429):
                time.sleep((2 ** i) + random.random())
                continue
            raise
        except (TimeoutError, socket.timeout):
            time.sleep((2 ** i) + random.random())
            continue



import os

from datetime import datetime
from pytz import timezone

def add_user_if_not_exists(user_id: int, username: str, first_name: str):
    service = get_google_service()
    sheet = service.spreadsheets()
    SHEET_ID = os.getenv("SHEET_ID")
    user_id = str(user_id or "")

    # 1) Пробуємо прочитати список існуючих ID (з ретраями)
    try:
        resp = _exec_with_retry(sheet.values().get(
            spreadsheetId=SHEET_ID,
            range="Користувачі!A2:A"   # без ліміту на 1000
        ))
        existing_ids = {row[0] for row in resp.get("values", []) if row}
    except Exception as e:
        # Не ламаємо потік, просто логуємо і вважаємо, що юзера ще нема
        print(f"[warn] read Користувачі!A2:A failed: {e}")
        existing_ids = set()

    if user_id in existing_ids:
        return

    # 2) Пишемо рядок (з ретраями)
    kyiv = timezone("Europe/Kyiv")
    now = datetime.now(kyiv).strftime("%Y-%m-%d %H:%M:%S")

    try:
        _exec_with_retry(sheet.values().append(
            spreadsheetId=SHEET_ID,
            range="Користувачі!A2:D2",
            valueInputOption="USER_ENTERED",
            body={"values": [[user_id, username or "", first_name or "", now]]}
        ))
    except Exception as e:
        # Теж не валимо основний запит
        print(f"[warn] append to Користувачі failed: {e}")



def find_film_by_name(film_name: str):
    service = get_google_service()
    sheet = service.spreadsheets()
    SHEET_ID = os.getenv("SHEET_ID")

    film_name_l = (film_name or "").lower().strip()

    # тягнемо всі назви без жорсткого ліміту
    result = _exec_with_retry(sheet.values().get(
        spreadsheetId=SHEET_ID,
        range="Sheet1!A2:A"
    ))
    rows = result.get("values", [])

    found_row_idx = None
    for idx, row in enumerate(rows):
        if row and film_name_l in row[0].lower():
            found_row_idx = idx + 2  # +2 бо починаємо з другого рядка
            break

    if not found_row_idx:
        return None

    film_row = _exec_with_retry(sheet.values().get(
        spreadsheetId=SHEET_ID,
        range=f"Sheet1!A{found_row_idx}:L{found_row_idx}"
    )).get("values", [[]])[0]

    return {
        "Назва":      film_row[0] if len(film_row) > 0 else "",
        "Тип":        film_row[1] if len(film_row) > 1 else "",
        "Жанр":       film_row[2] if len(film_row) > 2 else "",
        "Опис":       film_row[3] if len(film_row) > 3 else "",
        "Фото":       film_row[4] if len(film_row) > 4 else "",
        "message_id": film_row[5] if len(film_row) > 5 else "",
        "Добірка":    film_row[6] if len(film_row) > 6 else "",
        "Країна":     film_row[7] if len(film_row) > 7 else "",
        "Рік":        film_row[8] if len(film_row) > 8 else "",
        "file_id":    film_row[9] if len(film_row) > 9 else "",
        "Доступ":     film_row[10] if len(film_row) > 10 else "",
        "IMDb":       film_row[11] if len(film_row) > 11 else "",
    }

    return None
