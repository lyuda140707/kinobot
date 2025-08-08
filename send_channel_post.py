import os
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

def main():
    token = os.getenv('BOT_TOKEN')
    channels = ["@KinoTochkaUA", "@KinoTochkaFilms"]  # список каналів

    bot = Bot(token=token)

    qr_path = "qr.png"

    text = (
        "🎬 Привіт! Саме час поділитися нашим ботом 🎉\n\n"
        "📲 Скануй QR-код або тисни кнопку нижче, щоб перейти до бота\n"
        "👇👇👇"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔓 Відкрити", url="https://t.me/RelaxBox_UA_bot")]
    ])

    with open(qr_path, 'rb') as photo:
        for channel in channels:
            bot.send_photo(
                chat_id=channel,
                photo=photo,
                caption=text,
                reply_markup=keyboard
            )

if __name__ == '__main__':
    main()
