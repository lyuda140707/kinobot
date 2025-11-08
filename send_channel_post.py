import os
import asyncio
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

async def main():
    token = os.getenv('BOT_TOKEN')
    if not token:
        raise RuntimeError("ENV BOT_TOKEN не заданий")

    bot = Bot(token=token)

    # 🎬 Актуальні канали
    channels = ["@KinoTochkaFilms1", "@KinoTochkaUA"]

    # 🎯 Унікальні посилання для кожного каналу
    links = {
        "@KinoTochkaFilms1": "https://relaxbox.fun/films/promo",
        "@KinoTochkaUA": "https://relaxbox.fun/series/promo"
    }

    # 🩷 Твій текст-заклик (універсальний і безпечний)
    text = (
        "🍿 Хапай попкорн і заходь до нас 🎬\n"
        "Тут щодня нові фільми й серіали без реклами, як треба 😎\n\n"
        "🎥 Тисни кнопку нижче і дивись у боті 👇"
    )

    for ch in channels:
        button_url = links[ch]
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔓 Відкрити в боті", url=button_url)]
        ])

        try:
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
