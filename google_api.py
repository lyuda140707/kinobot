import gspread
import os
import json
from oauth2client.service_account import ServiceAccountCredentials
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build


def get_gsheet_data():
    creds_json = os.getenv("GOOGLE_SHEETS_CREDENTIALS_JSON")
    creds_dict = json.loads(creds_json)

    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)

    sheet_id = os.getenv("SHEET_ID")
    sheet = client.open_by_key(sheet_id).sheet1
    return sheet.get_all_records()

def get_google_service():
    creds_dict = json.loads(os.getenv("GOOGLE_SHEETS_CREDENTIALS_JSON"))
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)

    service = build("sheets", "v4", credentials=creds)
    return service
