import os
import asyncio
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

async def main():
    token = os.getenv('BOT_TOKEN')
    bot = Bot(token=token)

    channels = ["@KinoTochkaUA", "@KinoTochkaFilms"]
    qr_path = "qr.png"

    text = (
        "🎬 Привіт! Саме час поділитися нашим ботом 🎉\n\n"
        "📲 Скануй QR-код або тисни кнопку нижче, щоб перейти до бота\n"
        "👇👇👇"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔓 Відкрити", url="https://t.me/RelaxBox_UA_bot")]
    ])

    for ch in channels:
        try:
            with open(qr_path, 'rb') as photo:
                await bot.send_photo(
                    chat_id=ch,
                    photo=photo,
                    caption=text,
                    reply_markup=keyboard
                )
                print(f"✅ Надіслано у {ch}")
        except Exception as e:
            print(f"❌ Помилка у {ch}: {e}")

if __name__ == '__main__':
    asyncio.run(main())
