import logging
import asyncio
import textwrap

from vkbottle.bot import Message
from env.config import bot

from handlers import admin, manager, order, review
from keyboards.keyboards import main_kb
from services.google_sheet import get_user_orders

logging.basicConfig(level=logging.INFO)


# --- ОБРАБОТЧИКИ МЕНЮ ---
@bot.on.message(text="🔍 Мои заказы")
async def view_orders(message: Message):
    loading = await message.answer("Ищу ваши заказы... ⏳")
    orders = await asyncio.to_thread(get_user_orders, message.from_id)

    if not orders:
        await message.answer("У вас пока нет активных заказов. Нажмите «🚗 Новый заказ», чтобы оформить первый!")
        return

    text = "📂 Ваши последние заказы:\n\n"
    for row in orders:
        status = row[11] if len(row) > 11 else "В обработке"
        price = row[12] if (len(row) > 12 and row[12]) else "Уточняется"
        text += f"🔹 Заявка №{row[1]}\nСтатус: {status}\nЦена: {price}\nVIN: {row[8]}\nАвтомобиль: {row[9]}\nМенеджер: {row[6]}\n\n"

    await message.answer(text)


@bot.on.message(text="🚚 Доставка и оплата")
async def info_delivery(message: Message):
    text = textwrap.dedent("""
        💳 ОПЛАТА
        Все платежи осуществляются по 100% предоплате. Выбирайте наиболее удобный для вас вариант:

        💵 Наличные (для жителей Набережных Челнов).
        💳 Оплата по ссылке (интернет-эквайринг) или удобные переводы.
        ...
        (твой текст)
    """).strip()

    await message.answer(text)


@bot.on.message(text="📍 Наши контакты")
async def info_contacts(message: Message):
    text = (
        "💬 Наши контакты:\n\n"
        "👨‍💻 Руководитель Радик:\n"
        "• Telegram: @radga12\n"
        "• Max: +79635454655 \n"
        "• VK: https://vk.ru/radga02\n\n"
        "👨‍💻 Менеджер Никита:\n"
        "• Telegram: @Samyydobryy853\n"
        "• Телефон: +79196470069\n"
    )
    await message.answer(text)


# Хэндлер-заглушка СТРОГО в самом низу!
@bot.on.message()
async def fallback(message: Message):
    if not message.state_peer:
        await message.answer("Воспользуйтесь меню или напишите @radga12", keyboard=main_kb)


# --- ЗАПУСК ---
if __name__ == "__main__":
    bot.run_forever()