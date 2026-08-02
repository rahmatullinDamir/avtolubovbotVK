import asyncio
from datetime import datetime

from vkbottle.bot import Message
from vkbottle.dispatch.rules.base import StateRule

from main import bot  # Импортируем инстанс бота
from env.config import MANAGER_CHAT_ID, MSK
from services.helpers import abandoned_cart_timer, decode_vin, is_night_time
from keyboards.keyboards import main_kb, cancel_kb, process_vin_kb, contact_and_cancel_kb, manager_kb, confirm_kb, \
    role_kb
from services.google_sheet import get_cached_car_info, export_to_google_sheet
from states.FSM import OrderForm


# === СТАРТ И ВЫБОР РОЛИ ===
@bot.on.message(text=["Начать", "Старт", "Start"], state="*")
async def cmd_start(message: Message):
    await bot.state_dispenser.delete(message.peer_id)  # Очищаем стейты

    # В ВК нет удобного способа узнать откуда пришел юзер по рефке в обычном сообщении, 
    # поэтому пока ставим "Прямой вход"
    source = "Прямой вход"
    await bot.state_dispenser.set(message.peer_id, state=None, source=source)

    # Получаем имя пользователя через API ВК
    users_info = await bot.api.users.get(message.from_id)
    first_name = users_info[0].first_name

    text = (
        f"Приветствую Вас, {first_name}, на связи Люси - ваш персональный помощник. "
        f"Я буду помогать Вам ориентироваться в нашем интернет-магазине.\n\n"
        f"Для начала подскажите, в качестве кого Вы к нам обращайтесь?"
    )
    await message.answer(text, keyboard=role_kb)


# Ловим payload (нажатие на инлайн кнопку выбора роли)
@bot.on.message(payload={"role": "person"}, state="*")
async def role_person_selected(message: Message):
    await message.answer("Отлично! Чем я могу вам помочь сегодня?\nВыберите нужное действие в меню ниже 👇",
                         keyboard=main_kb)


@bot.on.message(payload={"role": "company"}, state="*")
async def role_company_selected(message: Message):
    await message.answer(
        "Приветствую корпоративного клиента! 🤝 Сейчас эта функция в разработке. Появится позже. Приносим извинения.")


# ======================================

@bot.on.message(text="❌ Отменить заказ", state="*")
async def cancel_order(message: Message):
    await bot.state_dispenser.delete(message.peer_id)
    await message.answer("Действие отменено 🚫", keyboard=main_kb)


@bot.on.message(text="🚗 Новый заказ", state="*")
async def start_order(message: Message):
    # Получаем данные из стейта, если они есть
    state_data = await bot.state_dispenser.get(message.peer_id)
    source = state_data.payload.get("source", "Прямой вход") if state_data else "Прямой вход"

    # Запускаем таймер брошенной корзины
    # В ВК нужно передать message.peer_id вместо chat_id
    asyncio.create_task(abandoned_cart_timer(message.peer_id))

    # Устанавливаем новый стейт и прокидываем туда source
    await bot.state_dispenser.set(message.peer_id, OrderForm.waiting_for_vin, source=source)
    await message.answer("Для начала напишите VIN-номер (17 символов):", keyboard=cancel_kb)


@bot.on.message(state=OrderForm.waiting_for_vin)
async def process_vin(message: Message):
    # Если нажали кнопку из инлайн-клавиатуры
    if message.payload:
        cmd = message.get_payload_json().get("cmd")
        state_data = await bot.state_dispenser.get(message.peer_id)

        if cmd == "vin_correct":
            car_info = state_data.payload.get("car_info")
            await message.answer(f"🚗 Авто: {car_info} ✅\n\nКакие запчасти нужны? (Можно текстом или фото)",
                                 keyboard=cancel_kb)
            await bot.state_dispenser.set(message.peer_id, OrderForm.waiting_for_details, **state_data.payload)
            return
        elif cmd == "vin_manual":
            await message.answer("✏️ Ручной ввод автомобиля\nНапишите марку, модель и год выпуска вашего автомобиля:",
                                 keyboard=cancel_kb)
            await bot.state_dispenser.set(message.peer_id, OrderForm.waiting_for_car_info_edit, **state_data.payload)
            return

    # Обычный ввод VIN
    vin = message.text.strip().upper()
    if len(vin) != 17 or not vin.isalnum():
        await message.answer(f"⚠️ Ошибка. Нужно ровно 17 символов. Вы прислали {len(vin)}.")
        return

    # Сохраняем VIN
    state_data = await bot.state_dispenser.get(message.peer_id)
    payload = state_data.payload if state_data else {}
    payload["vin"] = vin
    await bot.state_dispenser.set(message.peer_id, OrderForm.waiting_for_vin, **payload)

    await message.answer("🔍 Секунду, проверяю информацию...")

    cached_car_info = await asyncio.to_thread(get_cached_car_info, vin)

    if cached_car_info:
        payload["car_info"] = cached_car_info
        await bot.state_dispenser.set(message.peer_id, OrderForm.waiting_for_vin, **payload)
        await message.answer(f"🚗 Нашел машину в нашей базе:\n{cached_car_info}\n\nВсё верно?", keyboard=process_vin_kb)
        return

    car_info = await decode_vin(vin)

    if car_info:
        payload["car_info"] = car_info
        await bot.state_dispenser.set(message.peer_id, OrderForm.waiting_for_vin, **payload)
        await message.answer(f"🚗 По VIN определено авто:\n{car_info}\n\nВсё верно?", keyboard=process_vin_kb)
    else:
        await message.answer(
            "⚠️ Не удалось автоматически определить авто по VIN.\nПожалуйста, напишите марку, модель и год выпуска вручную:\n(вводится 1 раз при первом заказе)",
            keyboard=cancel_kb)
        await bot.state_dispenser.set(message.peer_id, OrderForm.waiting_for_car_info_edit, **payload)


@bot.on.message(state=OrderForm.waiting_for_car_info_edit)
async def process_manual_car_info(message: Message):
    state_data = await bot.state_dispenser.get(message.peer_id)
    payload = state_data.payload
    payload["car_info"] = message.text.strip()

    await bot.state_dispenser.set(message.peer_id, OrderForm.waiting_for_details, **payload)
    await message.answer("Какие запчасти нужны? (Можно текстом или фото)", keyboard=cancel_kb)


@bot.on.message(state=OrderForm.waiting_for_details)
async def process_details(message: Message):
    state_data = await bot.state_dispenser.get(message.peer_id)
    payload = state_data.payload

    # В ВК все фото и файлы лежат в message.attachments
    attachments = []
    if message.attachments:
        # Сохраняем "внутренние" ссылки ВК на фото для пересылки
        for attach in message.attachments:
            if attach.photo:
                attachments.append(f"photo{attach.photo.owner_id}_{attach.photo.id}")
            elif attach.doc:
                attachments.append(f"doc{attach.doc.owner_id}_{attach.doc.id}")

    details_text = message.text if message.text else "📎 Файл"

    payload["details"] = details_text
    payload["attachments"] = attachments

    await bot.state_dispenser.set(message.peer_id, OrderForm.waiting_for_city, **payload)
    await message.answer("В какой город доставка?", keyboard=cancel_kb)


@bot.on.message(state=OrderForm.waiting_for_city)
async def process_city(message: Message):
    state_data = await bot.state_dispenser.get(message.peer_id)
    payload = state_data.payload
    payload["city"] = message.text.strip()

    await bot.state_dispenser.set(message.peer_id, OrderForm.waiting_for_contact, **payload)
    await message.answer("Поделитесь контактом для связи (введите номер телефона):", keyboard=contact_and_cancel_kb)


@bot.on.message(state=OrderForm.waiting_for_contact)
async def process_contact(message: Message):
    state_data = await bot.state_dispenser.get(message.peer_id)
    payload = state_data.payload

    # Убираем все лишние символы из номера
    phone = ''.join(filter(str.isdigit, message.text))
    payload["phone"] = phone

    await bot.state_dispenser.set(message.peer_id, OrderForm.waiting_for_manager, **payload)
    await message.answer("Выберите менеджера:", keyboard=manager_kb)


@bot.on.message(state=OrderForm.waiting_for_manager)
async def process_manager_select(message: Message):
    state_data = await bot.state_dispenser.get(message.peer_id)
    payload = state_data.payload
    payload["manager"] = message.text

    text = (f"📝 Проверка:\n"
            f"• Ваш номер телефона: +{payload['phone']}\n"
            f"• Менеджер: {payload['manager']}\n"
            f"• Город: {payload['city']}\n"
            f"• VIN: {payload['vin']}\n"
            f"• Автомобиль: {payload.get('car_info', 'не определено')}\n"
            f"• Запрос: {payload['details']}\nВсё верно?")

    await bot.state_dispenser.set(message.peer_id, OrderForm.waiting_for_confirmation, **payload)
    await message.answer(text, keyboard=confirm_kb)


@bot.on.message(state=OrderForm.waiting_for_confirmation, text="✅ Всё верно, отправить")
async def process_confirm(message: Message):
    state_data = await bot.state_dispenser.get(message.peer_id)
    data = state_data.payload

    users_info = await bot.api.users.get(message.from_id, fields=["screen_name"])
    user = users_info[0]
    username = f"@{user.screen_name}" if user.screen_name else f"vk.com/id{user.id}"

    tags = {"👨‍💻 Менеджер Радик": "@radga12", "👨‍💻 Менеджер Никита": "@Samyydobryy853"}
    ping = tags.get(data['manager'], "@radga12 @Samyydobryy853")

    sheet_row = [
        datetime.now(MSK).strftime("%Y-%m-%d %H:%M:%S"),  # A
        str(message.from_id),  # C: В ВК это from_id (ID юзера)
        user.first_name,  # D: Имя
        f"+{data['phone']}",  # E
        username,  # F: Username VK
        ping,  # G
        data['city'],  # H
        data['vin'],  # I
        data.get('car_info', 'Не определено'),  # J
        data['details'],  # K
        "Новая 🟡",  # L
        "",  # M
        data.get('source', 'Прямой'),  # N
        "",  # O
        ""  # P
    ]

    order_id = await asyncio.to_thread(export_to_google_sheet, sheet_row)

    order_text = (f"📦 Заявка № {order_id}\n"
                  f"👤 Менеджер: {data['manager']} {ping}\n\n"
                  f"Клиент: {user.first_name}\n"
                  f"Тел: +{data['phone']}\n"
                  f"Город: {data['city']}\n"
                  f"Авто: {data.get('car_info')}\n"
                  f"VIN: {data['vin']}\n"
                  f"Запрос: {data['details']}\n"
                  f"Источник: {data.get('source')}")

    # Отправка менеджеру в ВК (в беседу или в ЛС)
    # В ВК attach_str должен быть в формате "photo123_456,doc123_456"
    attach_str = ",".join(data.get("attachments", []))

    try:
        await bot.api.messages.send(
            peer_id=MANAGER_CHAT_ID,
            message=order_text,
            attachment=attach_str,
            random_id=0
        )
    except Exception as e:
        print(f"Ошибка отправки менеджерам: {e}")

    msg = f"✅ Заявка № {order_id} отправлена!"
    if is_night_time():
        msg += "\n\n🌙 Сейчас мы закрыты, ответим утром!"
    else:
        msg += "\n\n🕐 Менеджер свяжется с вами в течение получаса для уточнения деталей заказа..."

    await message.answer(msg, keyboard=main_kb)
    await bot.state_dispenser.delete(message.peer_id)


@bot.on.message(state=OrderForm.waiting_for_confirmation, text="✏️ Заполнить заново")
async def restart_order_button(message: Message):
    await start_order(message)