# supabase_api.py
import os
import requests

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON = os.getenv("SUPABASE_ANON_KEY")

def _headers():
    return {
        "apikey": SUPABASE_ANON,
        "Authorization": f"Bearer {SUPABASE_ANON}",
    }



def get_films():
    """
    Повертає масив у ТВОЄМУ форматі:
    'Назва','Тип','Жанр','Опис','Фото','IMDb','Добірка','Доступ','Країна','Рік','message_id','Сезон','Серія'
    """
    url = (
        f"{SUPABASE_URL}/rest/v1/films"
        "?select=title,type,genre,description,photo,message_id,collection,country,year,access,imdb,season,episode"
    )
    r = requests.get(url, headers=_headers(), timeout=20)
    r.raise_for_status()
    rows = r.json()
    return [
        {
            "Назва"     : row.get("title", "") or "",
            "Тип"       : row.get("type", "") or "",
            "Жанр"      : row.get("genre", "") or "",
            "Опис"      : row.get("description", "") or "",
            "Фото"      : row.get("photo", "") or "",
            "IMDb"      : row.get("imdb", "") or "",
            "Добірка"   : row.get("collection", "") or "",
            "Доступ"    : row.get("access", "") or "",
            "Країна"    : row.get("country", "") or "",
            "Рік"       : row.get("year", "") or "",
            "message_id": row.get("message_id", "") or "",
            "Сезон"     : row.get("season", "") or "",
            "Серія"     : row.get("episode", "") or "",
        }
        for row in rows
    ]
def sb_update_fileid_by_message_id(msg_id, file_id):
    """
    Оновлює поле file_id у таблиці 'films' для конкретного message_id (int8)
    """
    import requests
    import urllib.parse

    print(f"🧩 [DEBUG] sb_update_fileid_by_message_id викликано для message_id={msg_id}, file_id={file_id}")
    try:
        # ✅ Перетворюємо у число (бо в Supabase message_id — int8)
        msg_id_int = int(msg_id)
        msg_q = urllib.parse.quote(str(msg_id_int))
        url = f"{SUPABASE_URL}/rest/v1/films?message_id=eq.{msg_q}"

        headers = {
            "apikey": SUPABASE_ANON,
            "Authorization": f"Bearer {SUPABASE_ANON}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }

        payload = {"file_id": file_id}
        r = requests.patch(url, headers=headers, json=payload, timeout=20)

        # 🧠 Логування відповіді
        if r.ok:
            print(f"✅ [Supabase] Оновлено file_id для message_id={msg_id_int}")
        else:
            print(f"⚠️ [Supabase] Помилка оновлення ({r.status_code}): {r.text}")

    except Exception as e:
        print(f"❌ [Supabase] Помилка оновлення: {e}")



# 🚀 Перевірка доступу до Supabase при старті сервера
if __name__ == "__main__":
    import requests

    print("🧩 Testing Supabase connection...")
    try:
        url = f"{SUPABASE_URL}/rest/v1/films?select=message_id&limit=1"
        headers = {
            "apikey": SUPABASE_ANON,
            "Authorization": f"Bearer {SUPABASE_ANON}"
        }
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            print("✅ Supabase доступний — з’єднання працює.")
        else:
            print(f"⚠️ Supabase відповів помилкою ({r.status_code}): {r.text}")
    except Exception as e:
        print(f"❌ Немає доступу до Supabase: {e}")

