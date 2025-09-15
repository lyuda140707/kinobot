from google_api import get_google_service
import os
from datetime import datetime, timedelta
from pytz import timezone
from utils.date_utils import safe_parse_date
import logging

logger = logging.getLogger(__name__)


def has_active_pro(user_id: str) -> bool:
    """
    Перевіряє, чи має користувач PRO:
    - Якщо expire_date ≥ сьогодні: повертає True.
    - Якщо прострочено: оновлює статус у Google Sheet на "Не активовано" і повертає False.
    """
    service = get_google_service()
    sheet = service.spreadsheets()
    sheet_id = os.getenv("SHEET_ID")

    res = sheet.values().get(
        spreadsheetId=sheet_id,
        range="PRO!A2:D1000"
    ).execute()
    rows = res.get("values", [])

    kyiv = timezone("Europe/Kyiv")
    today = datetime.now(kyiv).date()

    for idx, row in enumerate(rows, start=2):
        if len(row) < 4:
            continue

        uid, _, status, exp_str = row[:4]
        if str(user_id) != uid or status.strip().lower() != "активно":
            continue

        try:
            dt = safe_parse_date(exp_str)
        except Exception as e:
            logger.warning(f"Не вдалося розпарсити дату '{exp_str}' у рядку {idx}: {e}")
            continue

        exp_date = dt.date() if isinstance(dt, datetime) else dt

        if exp_date > today:
            return True

        # Якщо прострочено — оновлюємо статус
        try:
            sheet.values().update(
                spreadsheetId=sheet_id,
                range=f"PRO!C{idx}",
                valueInputOption="RAW",
                body={"values": [["Не активовано"]]}
            ).execute()
            logger.info(f"⛔ PRO закінчився для {user_id} у рядку {idx} — статус змінено")
        except Exception as e:
            logger.error(f"Не вдалося оновити статус для {user_id} у рядку {idx}: {e}")
        return False

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

    res = sheet.values().get(
        spreadsheetId=sheet_id,
        range="PRO!A2:D1000"
    ).execute()
    rows = res.get("values", [])

    kyiv = timezone("Europe/Kyiv")
    now = datetime.now(kyiv)
    expire_date = (now + timedelta(days=days)).strftime("%Y-%m-%d")

    # Якщо користувач вже є — оновлюємо рядок
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

    # Якщо немає — додаємо новий рядок
    sheet.values().append(
        spreadsheetId=sheet_id,
        range="PRO!A2:D2",
        valueInputOption="USER_ENTERED",
        body={"values": [[user_id, "", "Активно", expire_date]]}
    ).execute()
    logger.info(f"✅ PRO створено для {user_id} до {expire_date}")
    return True
