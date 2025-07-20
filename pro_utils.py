from google_api import get_google_service
import os
from datetime import datetime
from pytz import timezone
from app import safe_parse_date  # якщо функція вже є в app.py

def has_active_pro(user_id: int) -> bool:
    service = get_google_service()
    sheet = service.spreadsheets()
    SHEET_ID = os.getenv("SHEET_ID")

    result = sheet.values().get(
        spreadsheetId=SHEET_ID,
        range="PRO!A2:C1000"
    ).execute()

    rows = result.get("values", [])
    kyiv = timezone("Europe/Kyiv")
    now = datetime.now(kyiv)

    for row in rows:
        if len(row) < 2:
            continue
        uid, start_date = row[0], row[1]
        if str(user_id) == uid:
            try:
                start = safe_parse_date(start_date).replace(tzinfo=kyiv)
                if (now - start).days < 30:
                    return True
            except:
                pass
    return False
