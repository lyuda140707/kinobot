import gspread
import os
import json
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# Підключення до таблиці
def connect_to_sheet(sheet_name: str):
    creds_json = os.getenv("GOOGLE_SHEETS_CREDENTIALS_JSON")
    creds_dict = json.loads(creds_json)

    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)

    sheet_id = os.getenv("SHEET_ID")  # Отримуємо ID таблиці
    file = client.open_by_key(sheet_id)  # Відкриваємо таблицю за ID
    worksheet = file.worksheet(sheet_name)  # Відкриваємо аркуш за назвою (наприклад "Statistics")
    return worksheet


# Отримати дані з головної таблиці (фільми)
def get_gsheet_data():
    creds_json = os.getenv("GOOGLE_SHEETS_CREDENTIALS_JSON")
    creds_dict = json.loads(creds_json)

    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)

    sheet_id = os.getenv("SHEET_ID")
    sheet = client.open_by_key(sheet_id).sheet1
    return sheet.get_all_records()

# Зберегти статистику
def save_statistics(user_id: int):
    sheet = connect_to_sheet("Statistics")  # Назва твоєї таблиці
    records = sheet.get_all_records()
    user_ids = [str(record.get("user_id")) for record in records]

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if str(user_id) in user_ids:
        # Якщо юзер вже є, збільшуємо кількість заходів
        idx = user_ids.index(str(user_id)) + 2  # +2 бо в Sheets індексація з 1 і є заголовок
        current_visits = int(sheet.cell(idx, 3).value)  # Третя колонка - Відвідувань
        sheet.update_cell(idx, 3, current_visits + 1)
        sheet.update_cell(idx, 4, now)  # Час останнього візиту
    else:
        # Якщо юзера ще немає, додаємо нового
        sheet.append_row([str(user_id), now, 1, now])
