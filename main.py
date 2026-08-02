import logging
import asyncio
import textwrap

from vkbottle.bot import Bot, Message
from env.config import VK_TOKEN  # Убедись, что добавил токен сообщества в конфиг
from keyboards.keyboards import main_kb
from services.google_sheet import get_user_orders

logging.basicConfig(level=logging.INFO)

bot = Bot(token=VK_TOKEN)


# --- ОБРАБОТЧИКИ МЕНЮ ---
@bot.on.message(text="🔍 Мои заказы")
async def view_orders(message: Message):
    # message.from_id - это аналог message.from_user.id
    loading = await message.answer("Ищу ваши заказы... ⏳")
    orders = await asyncio.to_thread(get_user_orders, message.from_id)

    # В ВК нет удобного метода .delete() для своих сообщений,
    # поэтому мы просто отправляем новое сообщение поверх

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

        🟡 Оплата через Яндекс.Пэй:
        • Оплата частями через сервис Сплит.
        • Оплата картой Пэй с кешбэком баллами.
        • Оплата привязанными картами любых других банков за пару секунд.

        🏢 Для юридических лиц доступны безналичные перечисления.

        📦 ДОСТАВКА
        Мы ценим ваше время, поэтому предлагаем быструю доставку от 1 дня:

        🏃‍♂️ Самовывоз — заберите заказ самостоятельно.
        🟢 СДЭК — быстрая доставка прямо в руки.
        🟡 Яндекс.Маркет — доставка до удобного вам пункта выдачи (ПВЗ).
        🔵 Озон.Доставка — курьерская доставка прямо в руки.
        🚕 Яндекс.Такси — экспресс-доставка для Набережных Челнов и ближайших районов.

        🔄 ВОЗВРАТ
        Информация по возврату рассчитывается индивидуально. Если у вас возникли вопросы, пожалуйста, напишите нашему менеджеру: @radga12
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


# Хэндлер-заглушка для неизвестных команд
@bot.on.message()
async def fallback(message: Message):
    # Если сообщение не попало ни в один хэндлер выше и нет активного State
    if not message.state_peer:
        await message.answer("Воспользуйтесь меню или напишите @radga12", keyboard=main_kb)


# --- ЗАПУСК ---
if __name__ == "__main__":
    bot.run_forever()