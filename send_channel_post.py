import os
import asyncio
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

async def main():
    token = os.getenv('BOT_TOKEN')
    if not token:
        raise RuntimeError("ENV BOT_TOKEN не заданий")

    bot = Bot(token=token)

    # 🎬 Канали для постингу
    channels = ["@KinoTochkaFilms1", "@KinoTochkaUA"]

    # 🎯 Унікальні посилання на бот для кожного каналу
    links = {
        "@KinoTochkaFilms1": "https://relaxbox.fun/films/promo",
        "@KinoTochkaUA": "https://relaxbox.fun/series/promo"
    }

    # 🔥 Оновлений безпечний текст
    text = (
        "🍿 На нашому сайті — ще більше фільмів та серіалів!\n"
        "Щодня з'являються нові оновлення, добірки та прем’єри 💫\n\n"
        "✨ Дивитись можна з будь-якого пристрою: телефону, планшету чи комп’ютера — "
        "усе працює так само зручно, як у боті.\n\n"
        "🌐 Якщо заходиш на сайт — PRO діє автоматично.\n"
        "Вхід через Telegram, тому підписка одразу підтягнеться.\n\n"
        "👇 Обирай, де зручніше:"
    )

    for ch in channels:
        button_url = links[ch]

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔓 Відкрити в боті", url=button_url)],
            [InlineKeyboardButton("🌐 Відкрити сайт", url="https://kino-site.top/")]
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
