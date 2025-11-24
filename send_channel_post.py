import os
import asyncio
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

async def main():
    token = os.getenv('BOT_TOKEN')
    if not token:
        raise RuntimeError("ENV BOT_TOKEN не заданий")

    bot = Bot(token=token)

    # 🔹 Канали, куди відправляємо пост
    channels = ["@KinoTochkaFilms1", "@KinoTochkaUA"]

    # 🔹 Окремі посилання на бот (якщо хочеш — можу змінити)
    links = {
        "@KinoTochkaFilms1": "https://relaxbox.fun/films/promo",
        "@KinoTochkaUA": "https://relaxbox.fun/series/promo"
    }

    # 🔥 Твій текст — безпечний і максимально легальний
    text = (
        "🎬 Додаємо більше фільмів та серіалів!\n"
        "Щоб усе не завалювало бот — частину каталогу ми перенесли на сайт.\n\n"
        "🌐 Сайт працює через Telegram-авторизацію.\n"
        "Якщо маєш PRO — доступ автоматично активується і там.\n\n"
        "Обирай, де тобі зручніше дивитись 👇"
    )

    # 🔘 Кнопки
    for ch in channels:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔓 Дивитись у боті", url=links[ch])],
            [InlineKeyboardButton("🌐 Відкрити сайт", url="https://kino-site.top/")]
        ])

        try:
            await bot.send_message(
                chat_id=ch,
                text=text,
                reply_markup=keyboard,
                disable_web_page_preview=True
            )
            print(f"✅ Успішно надіслано у {ch}")
        except Exception as e:
            print(f"❌ Помилка у {ch}: {e}")

if __name__ == '__main__':
    asyncio.run(main())
