from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
import os

def main():
    token = os.getenv('BOT_TOKEN')
    channel = os.getenv('CHANNEL_ID')  # наприклад: "@RelaxBoxUA"

    bot = Bot(token=token)

    qr_path = "qr.png"  # бо він у корені, як і сам скрипт

    text = (
        "📲 Скануй QR-код або тисни кнопку нижче, щоб відкрити бота 🎬"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔓 Відкрити", url="https://t.me/RelaxBox_UA_bot")]
    ])

    with open(qr_path, 'rb') as photo:
        bot.send_photo(
            chat_id=channel,
            photo=photo,
            caption=text,
            reply_markup=keyboard
        )

if __name__ == '__main__':
    main()
