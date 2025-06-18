import os
import requests

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBAPP_URL = "https://t.me/UAKinoTochka_bot?startapp"

# Список каналів (можеш винести в .env як CHANNEL_LIST)
CHANNELS = ["@KinoTochkaUA", "@KinoTochkaFilms"]

TEXT = (
    "🎬 КіноБот уже тут!\n\n"
    "🍿 Знаходь найкращі фільми, серіали та мультфільми українською мовою 📺\n"
    "🔥 Все в одному застосунку — швидко, зручно!\n\n"
    "Натискай кнопку нижче і обирай, що подивитись сьогодні! 👇"
)

KEYBOARD = {
    "inline_keyboard": [[
        {"text": "🔙 Повернутись до бота", "url": WEBAPP_URL}
    ]]
}


def send_channel_post(channel_id):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": channel_id,
        "text": TEXT,
        "reply_markup": KEYBOARD
    }

    response = requests.post(url, json=payload)

    if response.status_code == 200:
        print(f"✅ Надіслано в {channel_id}")
    else:
        print(f"❌ Помилка для {channel_id}: {response.text}")


if __name__ == "__main__":
    for ch in CHANNELS:
        send_channel_post(ch)
