from google_api import get_google_service
import os
from datetime import datetime
from pytz import timezone
from utils.date_utils import safe_parse_date  # залишаємо
from google_api import get_google_service, fetch_with_retry

def has_active_pro(user_id: str) -> bool:
    service = get_google_service()
    SHEET_ID = os.getenv("SHEET_ID")
    result = fetch_with_retry(service, SHEET_ID, "PRO!A2:D10000")
    rows = result.get("values", [])
    kyiv = timezone("Europe/Kyiv")
    now = datetime.now(kyiv)
    for row in rows:
        if len(row) < 4:
            continue
        uid, _, status, expire_date_str = row[:4]
        if str(user_id) == uid and status.lower().strip() == "активно":
            try:
                expire = make_aware_if_needed(safe_parse_date(expire_date_str), tz_name="Europe/Kyiv")
                if expire >= now:
                    return True
            except:
                pass
    return False

def make_aware_if_needed(dt: datetime, tz_name="Europe/Kyiv") -> datetime:
    """Перетворює naive datetime на aware, якщо потрібно."""
    if dt.tzinfo is None:
        return timezone(tz_name).localize(dt)
    return dt
