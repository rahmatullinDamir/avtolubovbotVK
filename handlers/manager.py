import asyncio
import logging
import re

from vkbottle.bot import Message

from env.config import bot
from env.config import MANAGER_CHAT_ID
from keyboards.keyboards import create_nps_kb
from services.google_sheet import update_order_and_get_info, update_order_status, update_supplier_number_only

# Правило для фильтрации сообщений только из чата менеджеров
def is_manager_chat(message: Message) -> bool:
    return message.peer_id == MANAGER_CHAT_ID

@bot.on.message(func=is_manager_chat)
async def manager_update(message: Message):
    if not message.text:
        return

    text = message.text.lower()
    logging.info(f"Получено сообщение в чате менеджеров: {text}")

    order_match = re.search(r"заявка\s*(\d+)", text)

    if not order_match:
        return # Если нет слова "заявка X", просто игнорируем (менеджеры общаются между собой)

    order_id = order_match.group(1)

    # Ищем различные паттерны в тексте
    price_match = re.search(r"цена\s*(\d+)", text)
    sup_number_match = re.search(r"номер\s+(?:заказа\s+)?(?:у\s+)?поставщика\s+([a-zA-Z0-9_-]+)", text)

    tags = {"1956819432": "@radga12", "1121338444": "@Samyydobryy853"}
    # В ВК получаем инфу о том, кто написал сообщение в беседу
    users_info = await bot.api.users.get(message.from_id, fields=["screen_name"])
    user = users_info[0]
    actual_username = f"@{user.screen_name}" if user.screen_name else f"vk.com/id{user.id}"
    manager = tags.get(str(message.from_id), actual_username)

    # =========================================================
    # ПУТЬ 1: ПЕРВИЧНАЯ ОБРАБОТКА (УСТАНОВКА ЦЕНЫ)
    # =========================================================
    if price_match:
        price = price_match.group(1)

        supplier_match = re.search(r"поставщик\s+([а-яa-z0-9_-]+)", text)
        supplier = supplier_match.group(1) if supplier_match else ""
        supplier_order = sup_number_match.group(1) if sup_number_match else ""
        delivery_match = re.search(r"доставка\s*(\d+)", text)
        delivery_rub = int(delivery_match.group(1)) if delivery_match else 0

        user_id, manager_name = await asyncio.to_thread(
            update_order_and_get_info, order_id, price, manager, supplier, supplier_order, delivery_rub
        )

        if user_id:
            report = f"✅ Статус: Обработана\n💰 Цена: {price} руб."
            if delivery_rub > 0: report += f"\n🚚 Доставка: {delivery_rub} руб."
            if supplier: report += f"\n🏢 Поставщик: {supplier.title()}"
            if supplier_order: report += f"\n🔢 Номер заказа: {supplier_order}"

            await message.answer(f"Отчет по заявке №{order_id}:\n{report}")

            try:
                await bot.api.messages.send(
                    peer_id=int(user_id),
                    message=f"✅ Ваша заявка №{order_id} обработана!\n💰 Цена: {price} руб.",
                    random_id=0
                )
            except Exception as e:
                logging.error(f"Не удалось отправить Push клиенту: {e}")
        else:
            await message.answer(f"❌ Заявка №{order_id} не найдена в таблице (проверь колонку B).")

    # =========================================================
    # ПУТЬ 2: ТОЛЬКО ОБНОВЛЕНИЕ НОМЕРА ПОСТАВЩИКА
    # =========================================================
    elif sup_number_match and "статус" not in text:
        supplier_order = sup_number_match.group(1)

        success = await asyncio.to_thread(update_supplier_number_only, order_id, supplier_order)

        if success:
            await message.answer(f"✅ Номер заказа у поставщика ({supplier_order}) успешно сохранен в таблицу для заявки №{order_id}.")
        else:
            await message.answer(f"❌ Заявка №{order_id} не найдена в таблице.")

    # =========================================================
    # ПУТЬ 3: ОБНОВЛЕНИЕ СТАТУСОВ (БЕЗ ЦЕНЫ)
    # =========================================================
    else:
        raw_status = re.sub(r"заявка\s*\d+", "", text).strip()
        raw_status = re.sub(r"^статус\s+", "", raw_status).strip()

        if not raw_status:
            await message.answer("⚠️ Вы не указали статус. Напишите, например: заявка 14 статус ожидает оплаты")
            return

        status_formatted = raw_status.capitalize()
        if "склад" in raw_status:
            status_formatted = "На складе поставщика 📦"
        elif "доставк" in raw_status or "пути" in raw_status:
            status_formatted = "Передана в доставку 🚚"
        elif "закрыт" in raw_status or "получен" in raw_status:
            status_formatted = "Закрыта 🏁"
        elif "отменен" in raw_status:
            status_formatted = "Отменена ❌"
        elif "ожида" in raw_status or "оплат" in raw_status:
            status_formatted = "Ожидает оплаты ⏳"

        user_id = await asyncio.to_thread(update_order_status, order_id, status_formatted)

        if user_id:
            await message.answer(f"✅ Статус заявки №{order_id} изменен на:\n{status_formatted}")

            try:
                if "закрыт" in raw_status or "получен" in raw_status:
                    await bot.api.messages.send(
                        peer_id=int(user_id),
                        message=f"🔔 Ваш заказ №{order_id} успешно завершен! 🏁\n\nПожалуйста, оцените работу нашего магазина:",
                        keyboard=create_nps_kb(order_id),
                        random_id=0
                    )
                else:
                    await bot.api.messages.send(
                        peer_id=int(user_id),
                        message=f"🔔 Обновление по вашему заказу №{order_id}!\n\nТекущий статус: {status_formatted}",
                        random_id=0
                    )
            except Exception as e:
                logging.error(f"Не удалось отправить статус клиенту: {e}")
        else:
            await message.answer(f"❌ Заявка №{order_id} не найдена в таблице.")