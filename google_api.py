import os
import json
from datetime import datetime
from pytz import timezone

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

_GOOGLE_SERVICE = None
_SHEETS = None


def get_google_service():
    global _GOOGLE_SERVICE

    if _GOOGLE_SERVICE is not None:
        return _GOOGLE_SERVICE

    creds_json = os.getenv("GOOGLE_SHEETS_CREDENTIALS_JSON", "").strip()
    if not creds_json:
        raise RuntimeError("ENV GOOGLE_SHEETS_CREDENTIALS_JSON не заданий")

    creds_dict = json.loads(creds_json)

    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)

    _GOOGLE_SERVICE = build(
        "sheets",
        "v4",
        credentials=creds,
        cache_discovery=False
    )

    return _GOOGLE_SERVICE


def get_sheets():
    global _SHEETS

    if _SHEETS is None:
        _SHEETS = get_google_service().spreadsheets()

    return _SHEETS


def add_user_if_not_exists(user_id: int, username: str = "", first_name: str = ""):

    sheet_id = os.getenv("SHEET_ID", "").strip()
    if not sheet_id:
        raise RuntimeError("ENV SHEET_ID не заданий")

    sheets = get_sheets()

    res = sheets.values().get(
        spreadsheetId=sheet_id,
        range="Користувачі!A2:A2000"
    ).execute()

    existing_ids = {row[0] for row in res.get("values", []) if row and row[0]}

    if str(user_id) in existing_ids:
        return

    kyiv = timezone("Europe/Kyiv")
    now = datetime.now(kyiv).strftime("%Y-%m-%d %H:%M:%S")

    sheets.values().append(
        spreadsheetId=sheet_id,
        range="Користувачі!A2:D2",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": [[str(user_id), username or "", first_name or "", now]]}
    ).execute()


def find_film_by_name(query: str):

    query = (query or "").strip()

    if not query:
        return None

    supa = _find_film_supabase(query)

    if supa is not None:
        return supa

    return _find_film_gsheets(query)


def _find_film_supabase(query: str):

    import urllib.parse
    import requests

    supabase_url = os.getenv("SUPABASE_URL", "").rstrip("/")
    supabase_key = (
        os.getenv("SUPABASE_SERVICE_KEY")
        or os.getenv("SUPABASE_KEY")
        or os.getenv("SUPABASE_ANON_KEY")
        or os.getenv("SUPABASE_ANON")
        or ""
    ).strip()

    if not supabase_url or not supabase_key:
        return None

    def sb_headers():
        return {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}"
        }

    q = urllib.parse.quote(f"*{query}*")

    url = f"{supabase_url}/rest/v1/films?select=*&title=ilike.{q}&limit=50"

    try:
        r = requests.get(url, headers=sb_headers(), timeout=10)

        if not r.ok:
            print(f"❌ Supabase error: {r.status_code} {r.text}")
            return None

        films = r.json() or []

        if not films:
            return None

        films_with_channel = [f for f in films if f.get("channel_id")]

        found = films_with_channel[0] if films_with_channel else films[0]

        return found

    except Exception as e:
        print("❌ Supabase request error:", e)
        return None


def _find_film_gsheets(film_name: str):

    sheet_id = os.getenv("SHEET_ID", "").strip()

    if not sheet_id:
        raise RuntimeError("ENV SHEET_ID не заданий")

    sheets = get_sheets()

    res = sheets.values().get(
        spreadsheetId=sheet_id,
        range="Sheet1!A2:A2000"
    ).execute()

    rows = res.get("values", [])

    found_row_idx = None
    needle = film_name.lower()

    for i, row in enumerate(rows, start=2):

        if row and row[0] and needle in row[0].lower():
            found_row_idx = i
            break

    if not found_row_idx:
        return None

    film_row = sheets.values().get(
        spreadsheetId=sheet_id,
        range=f"Sheet1!A{found_row_idx}:L{found_row_idx}"
    ).execute().get("values", [[]])[0]

    return {
        "Назва": film_row[0] if len(film_row) > 0 else "",
        "Тип": film_row[1] if len(film_row) > 1 else "",
        "Жанр": film_row[2] if len(film_row) > 2 else "",
        "Опис": film_row[3] if len(film_row) > 3 else "",
        "Фото": film_row[4] if len(film_row) > 4 else "",
        "message_id": film_row[5] if len(film_row) > 5 else "",
        "Добірка": film_row[6] if len(film_row) > 6 else "",
        "Країна": film_row[7] if len(film_row) > 7 else "",
        "Рік": film_row[8] if len(film_row) > 8 else "",
        "file_id": film_row[9] if len(film_row) > 9 else "",
        "Доступ": film_row[10] if len(film_row) > 10 else "",
        "IMDb": film_row[11] if len(film_row) > 11 else "",
    }
