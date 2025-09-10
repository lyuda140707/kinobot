from google_api import get_google_service
import os
from datetime import datetime
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
    # 1) Отримуємо доступ до Google Sheet
    service = get_google_service()
    sheet = service.spreadsheets()
    sheet_id = os.getenv("SHEET_ID")

    # 2) Зчитуємо всі записи
    res = sheet.values().get(
        spreadsheetId=sheet_id,
        range="PRO!A2:D1000"
    ).execute()
    rows = res.get("values", [])

    # 3) Готуємо дату «сьогодні» в Києві
    kyiv = timezone("Europe/Kyiv")
    today = datetime.now(kyiv).date()

    # 4) Перебираємо рядки (номер у таблиці = idx)
    for idx, row in enumerate(rows, start=2):
        if len(row) < 4:
            continue

        uid, _, status, exp_str = row[:4]
        if str(user_id) != uid or status.strip().lower() != "активно":
            continue

        # 5) Парсимо дату
        try:
            dt = safe_parse_date(exp_str)
        except Exception as e:
            logger.warning(f"Не вдалося розпарсити дату '{exp_str}' у рядку {idx}: {e}")
            continue

        exp_date = dt.date() if isinstance(dt, datetime) else dt

        # 6) Перевіряємо
        if exp_date > today:
            return True

        # 7) Якщо прострочено — оновлюємо статус і виходимо
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
