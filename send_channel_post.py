import asyncio
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

async def send_start_messages():
    # 🔗 Кнопка на бота
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎥 Відкрити RelaxBox", url="https://t.me/RelaxBoxBot?start=webapp")]
        ]
    )

    # 📢 Повідомлення для каналів
    message_text = (
        "🎬 <b>RelaxBox</b>\n"
        "Твій особистий кінозал у Telegram 💫\n\n"
        "🍿 Дивись фільми, серіали та мультфільми українською.\n"
        "👑 Отримуй PRO-доступ для повного каталогу!\n\n"
        "👉 Натисни, щоб запустити застосунок ↓"
    )

    # 🗂️ Список каналів
    channels = [
        -1002863248325,  # 🎬 RelaxTime View
        -1003153440872,  # 📺 RelaxBox | Серіали
        -1003160463240,  # 👑 PRO | Фільми
        -1003004556512,  # 👑 PRO | Серіали
    ]

    for ch in channels:
        try:
            msg = await bot.send_message(ch, message_text, parse_mode="HTML", reply_markup=keyboard)
            await bot.pin_chat_message(ch, msg.message_id, disable_notification=True)
            print(f"✅ Закріплено стартове повідомлення в каналі {ch}")
        except Exception as e:
            print(f"⚠️ Помилка для каналу {ch}: {e}")

# 🔹 Запускаємо після старту
if __name__ == "__main__":
    import asyncio
    async def main():
        print("🚀 Бот запущено!")
        await send_start_messages()  # ← додано тут (запустить один раз)
        await dp.start_polling(bot)
    asyncio.run(main())
