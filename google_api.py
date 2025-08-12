import os, json, time, random, socket
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from datetime import datetime
from pytz import timezone

# --- Читання (gspread) ---
def get_gsheet_data():
    creds_json = os.getenv("GOOGLE_SHEETS_CREDENTIALS_JSON")
    if not creds_json:
        raise RuntimeError("GOOGLE_SHEETS_CREDENTIALS_JSON is empty")
    creds_dict = json.loads(creds_json)

    scope = [
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/drive.readonly",
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)

    sheet_id = os.getenv("SHEET_ID")
    if not sheet_id:
        raise RuntimeError("SHEET_ID is empty")
    sheet = client.open_by_key(sheet_id).sheet1
    return sheet.get_all_records()

# --- Запис (googleapiclient) ---
_SERVICE = None
def get_google_service():
    """Singleton: будуємо один раз і кешуємо."""
    global _SERVICE
    if _SERVICE:
        return _SERVICE

    creds_json = os.getenv("GOOGLE_SHEETS_CREDENTIALS_JSON")
    if not creds_json:
        raise RuntimeError("GOOGLE_SHEETS_CREDENTIALS_JSON is empty")
    creds_dict = json.loads(creds_json)

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)

    # ❗ ТІЛЬКИ credentials, БЕЗ http=
    _SERVICE = build("sheets", "v4", credentials=creds, cache_discovery=False)
    return _SERVICE

def _exec_with_retry(request, tries=5):
    """Ретраї на 500/502/503/504/429 та таймаути."""
    for i in range(tries):
        try:
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

def add_user_if_not_exists(user_id: int, username: str, first_name: str):
    sheet = get_google_service().spreadsheets()
    SHEET_ID = os.getenv("SHEET_ID")
    user_id = str(user_id or "")

    try:
        resp = _exec_with_retry(sheet.values().get(
            spreadsheetId=SHEET_ID,
            range="Користувачі!A2:A"
        ))
        existing_ids = {row[0] for row in resp.get("values", []) if row}
    except Exception as e:
        print(f"[warn] read Користувачі!A2:A failed: {e}")
        existing_ids = set()

    if user_id in existing_ids:
        return

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
        print(f"[warn] append to Користувачі failed: {e}")

def find_film_by_name(film_name: str):
    sheet = get_google_service().spreadsheets()
    SHEET_ID = os.getenv("SHEET_ID")
    film_name_l = (film_name or "").lower().strip()

    result = _exec_with_retry(sheet.values().get(
        spreadsheetId=SHEET_ID,
        range="Sheet1!A2:A"
    ))
    rows = result.get("values", [])

    found_row_idx = None
    for idx, row in enumerate(rows):
        if row and film_name_l in row[0].lower():
            found_row_idx = idx + 2
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
