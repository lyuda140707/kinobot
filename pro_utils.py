from google_api import get_google_service
import os
from datetime import datetime
from pytz import timezone
from utils.date_utils import safe_parse_date

def has_active_pro(user_id: int) -> bool:
    service = get_google_service()
    sheet = service.spreadsheets()
    SHEET_ID = os.getenv("SHEET_ID")

    result = sheet.values().get(
        spreadsheetId=SHEET_ID,
        range="PRO!A2:D1000"
    ).execute()

    rows = result.get("values", [])
    kyiv = timezone("Europe/Kyiv")
    now = datetime.now(kyiv)

    for row in rows:
        if len(row) < 4:
            continue
        uid, _, status, expire_date_str = row[:4]
        if str(user_id) == uid and status.lower().strip() == "активно":
            try:
                expire = safe_parse_date(expire_date_str).replace(tzinfo=kyiv)
                if expire >= now:
                    return True
            except:
                pass
    return False
