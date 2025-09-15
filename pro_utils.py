from google_api import get_google_service
import os
from datetime import datetime, timedelta
from pytz import timezone
from utils.date_utils import safe_parse_date
import logging

logger = logging.getLogger(__name__)

def has_active_pro(user_id: str) -> bool:
    ...
    return False


def add_pro_user(user_id: str, days: int = 30):
    """
    Додає або продовжує PRO-доступ для користувача.
    Якщо користувач вже є в таблиці — оновлює дату.
    Якщо немає — створює новий запис.
    """
    service = get_google_service()
    sheet = service.spreadsheets()
    sheet_id = os.getenv("SHEET_ID")

    # 1) Зчитуємо поточні записи
    res = sheet.values().get(
        spreadsheetId=sheet_id,
        range="PRO!A2:D1000"
    ).execute()
    rows = res.get("values", [])

    kyiv = timezone("Europe/Kyiv")
    now = datetime.now(kyiv)
    expire_date = (now + timedelta(days=days)).strftime("%Y-%m-%d")

    # 2) Якщо користувач вже є — оновлюємо рядок
    for idx, row in enumerate(rows, start=2):
        if len(row) >= 1 and row[0] == str(user_id):
            username = row[1] if len(row) > 1 else ""
            sheet.values().update(
                spreadsheetId=sheet_id,
                range=f"PRO!A{idx}:D{idx}",
                valueInputOption="USER_ENTERED",
                body={"values": [[user_id, username, "Активно", expire_date]]}
            ).execute()
            logger.info(f"✅ PRO оновлено для {user_id} до {expire_date}")
            return True

    # 3) Якщо немає — додаємо новий рядок
    sheet.values().append(
        spreadsheetId=sheet_id,
        range="PRO!A2:D2",
        valueInputOption="USER_ENTERED",
        body={"values": [[user_id, "", "Активно", expire_date]]}
    ).execute()
    logger.info(f"✅ PRO створено для {user_id} до {expire_date}")
    return True
