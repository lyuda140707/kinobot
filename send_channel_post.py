import os
import requests

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBAPP_URL = "https://t.me/UAKinoTochka_bot?startapp"

# ✅ Лише новий канал
CHANNELS = ["@KinoTochkaFilms"]

def send_channel_post(channel_id):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": channel_id,
        "text": (
            "👀 А ти вже був у нашому кіно-застосунку?\n\n"
            "📱 Усе зібрано в одному місці: фільми, серіали, мультики — все українською!\n"
            "🎯 Зручно, без реклами, і працює прямо в Telegram!\n\n"
            "💥 Нові добірки вже чекають — не прогав 😉"
            
        ),
        "reply_markup": {
            "inline_keyboard": [[
                {"text": "🎬 Перейти до застосунку", "url": WEBAPP_URL}
            ]]
        }
    }

    response = requests.post(url, json=payload)

    if response.status_code == 200:
        print(f"✅ Успішно надіслано в {channel_id}")
    else:
        print(f"❌ Помилка при надсиланні в {channel_id}: {response.text}")

if __name__ == "__main__":
    for ch in CHANNELS:
        send_channel_post(ch)
