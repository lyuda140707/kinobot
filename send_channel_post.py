import os
import requests
import urllib.parse

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNELS  = ["@KinoTochkaFilms", "@KinoTochkaUA"]

BOT_URL        = "https://t.me/Relax_TimeBot"
SHARE_TEXT_RAW = "Рекомендую цей кіно-бот! Поділись з друзями👥"

# Формуємо коректне посилання для шерингу
params = {"url": BOT_URL, "text": SHARE_TEXT_RAW}
SHARE_URL = "https://t.me/share/url?" + urllib.parse.urlencode(
    params, quote_via=urllib.parse.quote_plus
)

def send_channel_post(channel_id):
    resp = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={
            "chat_id": channel_id,
            "text": (
                "🎉 Привіт, кіномани! 🍿\n"
                "Якщо наш бот вразив вас до глибини душі, не тримайте це в секреті — "
                "розкажіть про нього друзям! 😉\n\n"
                f"🤖 Бот: @{BOT_URL.split('/')[-1]}\n\n"
                "Буду безмежно вдячна за вашу підтримку та розкрутку моєї роботи! 🙏✨🚀"
            ),
            "reply_markup": {
                "inline_keyboard": [
                    [{"text": "🎬 Перейти до боту",   "url": BOT_URL + "?startapp"}],
                    [{"text": "📣 Поділитися ботом", "url": SHARE_URL}]
                ]
            }
        }
    )
    if resp.ok:
        print(f"✅ Успішно надіслано в {channel_id}")
    else:
        print(f"❌ Помилка в {channel_id}: {resp.text}")

if __name__ == "__main__":
    for ch in CHANNELS:
        send_channel_post(ch)
