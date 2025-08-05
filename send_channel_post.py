import os
import requests
import urllib.parse

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNELS  = ["@KinoTochkaFilms"]

# 1) Лінк на ваш бот
BOT_URL    = "https://t.me/Relax_TimeBot"
# 2) Текст, який підставиться у вікні шерингу
SHARE_TEXT = "Рекомендую%20цей%20кіно-бот!%20Поділись%20з%20друзями👥"

# Генеруємо URL для кнопки «Поділитися ботом»
SHARE_URL = (
    "https://t.me/share/url?"
    f"url={urllib.parse.quote_plus(BOT_URL)}"
    f"&text={SHARE_TEXT}"
)

def send_channel_post(channel_id):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": channel_id,
        "text": (
            "🎉 Привіт, кіномани! 🍿\n"
            "Якщо наш бот вразив вас до глибини душі, не тримайте це в секреті — "
            "розкажіть про нього друзям! 😉\n\n"
            "🤖 Бот: @Relax_TimeBot\n\n"
            "Буду безмежно вдячна за вашу підтримку та розкрутку моєї роботи! 🙏✨🚀"
        ),
        "reply_markup": {
            "inline_keyboard": [
                [
                    {"text": "🎬 Перейти до боту",         "url": BOT_URL + "?startapp"},
                ],
                [
                    {"text": "📣 Поділитися ботом",       "url": SHARE_URL}
                ]
            ]
        }
    }
    r = requests.post(url, json=payload)
    if r.ok:
        print(f"✅ Успішно надіслано в {channel_id}")
    else:
        print(f"❌ Помилка при надсиланні в {channel_id}: {r.text}")

if __name__ == "__main__":
    for ch in CHANNELS:
        send_channel_post(ch)
