import os
import requests

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")  # або напряму "@твій_канал"

WEBAPP_URL = "https://lyuda140707.github.io/kinobot-webapp/"

def send_channel_post():
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": CHANNEL_ID,
        "text": (
            "🎬 КіноБот уже тут!\n\n"
            "🍿 Знаходь найкращі фільми, серіали та мультфільми українською мовою 📺\n"
            "🔥 Все в одному застосунку — швидко, зручно ! \n\n"
            "Натискай кнопку нижче і обирай, що подивитись сьогодні! 👇"
        ),
        "reply_markup": {
            "inline_keyboard": [[
                {"text": "🎬 Перейти до застосунку", "url": WEBAPP_URL}
            ]]
        }
    }

    response = requests.post(url, json=payload)

    if response.status_code == 200:
        print("✅ Повідомлення успішно надіслано!")
    else:
        print(f"❌ Помилка: {response.text}")

if __name__ == "__main__":
    send_channel_post()
