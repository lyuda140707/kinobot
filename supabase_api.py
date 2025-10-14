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
