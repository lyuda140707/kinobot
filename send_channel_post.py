import os
import asyncio
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

async def main():
    token = os.getenv('BOT_TOKEN')
    if not token:
        raise RuntimeError("ENV BOT_TOKEN не заданий")

    bot = Bot(token=token)

    channels = ["@KinoTochkaUA", "@KinoTochkaFilms"]
    qr_path = "qr.png"

    # ✅ Прямий deep-link у Telegram
    button_url = "tg://resolve?domain=RelaxBox_UA_bot&start=promo"

    text = (
        "🍿 Привіт! Поділися кіношним настроєм 🎬\n"
        "Запроси друзів у наш бот — нехай теж мають, що дивитися 😉\n\n"
        "📲 Тисни кнопку або скануй QR-код і вперед! 🚀\n"
        "👇👇👇"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔓 Відкрити", url=button_url)]
    ])

    for ch in channels:
        try:
            if os.path.exists(qr_path):
                with open(qr_path, 'rb') as photo:
                    await bot.send_photo(
                        chat_id=ch,
                        photo=photo,
                        caption=text,
                        reply_markup=keyboard
                    )
            else:
                await bot.send_message(
                    chat_id=ch,
                    text=text,
                    reply_markup=keyboard,
                    disable_web_page_preview=True
                )
            print(f"✅ Надіслано у {ch}")
        except Exception as e:
            print(f"❌ Помилка у {ch}: {e}")

if __name__ == '__main__':
    asyncio.run(main())
