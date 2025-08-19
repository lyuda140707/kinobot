import os
import asyncio
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

async def main():
    token = os.getenv('BOT_TOKEN')
    if not token:
        raise RuntimeError("ENV BOT_TOKEN не заданий")

    bot = Bot(token=token)

    channels = ["@KinoTochkaUA", "@KinoTochkaFilms"]

    # ✅ Прямий запуск бота з deep-link (WebApp відкривається через /start)
    button_url = "tg://resolve?domain=RelaxBox_UA_bot&start=app"

    text = (
        "✨ А ти вже пробував наш застосунок? 😉\n\n"
        "🔎 Зручний пошук фільмів\n"
        "📂 Улюблене завжди під рукою\n"
        "🎥 Новинки щодня\n\n"
        "👇 Спробуй прямо зараз!"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📲 Відкрити застосунок", url=button_url)]
    ])

    for ch in channels:
        try:
            await bot.send_message(
                chat_id=ch,
                text=text,
                reply_markup=keyboard
            )
            print(f"✅ Надіслано у {ch}")
        except Exception as e:
            print(f"❌ Помилка у {ch}: {e}")

if __name__ == '__main__':
    asyncio.run(main())
