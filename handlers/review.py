import asyncio
import logging
import json

from vkbottle.bot import Message

from main import bot
from env.config import MANAGER_CHAT_ID, REVIEWS_CHAT_ID
from keyboards.keyboards import skip_kb, main_kb
from services.google_sheet import get_city_by_order_id
from states.FSM import ReviewForm


# Фильтр для отлова нажатия на звездочки (NPS)
def nps_filter(message: Message) -> bool:
    if message.payload:
        try:
            payload = json.loads(message.payload)
            return "nps" in payload
        except json.JSONDecodeError:
            pass
    return False


# --- ОБРАБОТКА ОЦЕНОК NPS ---
@bot.on.message(func=nps_filter, state="*")
async def process_nps(message: Message):
    payload = json.loads(message.payload)
    order_id = payload["order_id"]
    rating = int(payload["nps"])

    await message.answer(f"Вы поставили {rating} ⭐️. Спасибо за вашу оценку!")

    if rating < 3:
        alert_text = f"⚠️ ВНИМАНИЕ! НИЗКАЯ ОЦЕНКА ⚠️\n\nПользователь поставил {rating} ⭐️ по заявке №{order_id}. Свяжитесь с клиентом для урегулирования ситуации!"
        try:
            await bot.api.messages.send(peer_id=MANAGER_CHAT_ID, message=alert_text, random_id=0)
        except Exception as e:
            logging.error(f"Ошибка отправки алерта: {e}")
    else:
        await message.answer(
            "Будем очень признательны, если вы оставите отзыв о нашей работе! 📝\n\n"
            "Напишите пару слов, а также можете прикрепить фото или видео полученных запчастей. "
            "Ваш отзыв поможет другим водителям сделать правильный выбор.",
            keyboard=skip_kb
        )

        loop = asyncio.get_event_loop()
        city = await loop.run_in_executor(None, get_city_by_order_id, order_id)

        # Сохраняем данные в FSM
        await bot.state_dispenser.set(
            message.peer_id,
            ReviewForm.waiting_for_review,
            review_rating=rating,
            order_id=order_id,
            city=city
        )


@bot.on.message(payload={"cmd": "skip_review"}, state="*")
async def skip_review(message: Message):
    await bot.state_dispenser.delete(message.peer_id)
    await message.answer("Вы пропустили шаг с отзывом. Спасибо, что выбираете нас! ⚙️❤️", keyboard=main_kb)


@bot.on.message(state=ReviewForm.waiting_for_review)
async def process_review(message: Message):
    state_data = await bot.state_dispenser.get(message.peer_id)
    data = state_data.payload if state_data else {}

    rating = data.get("review_rating", 5)
    order_id = data.get("order_id", "Неизвестно")
    city = data.get("city", "Не указан")

    # Получаем имя клиента
    users_info = await bot.api.users.get(message.from_id, fields=["screen_name"])
    user = users_info[0]
    first_name = user.first_name
    if user.screen_name:
        first_name += f" (@{user.screen_name})"

    # Собираем фото и видео из ВК
    attachments = []
    if message.attachments:
        for attach in message.attachments:
            if attach.photo:
                attachments.append(f"photo{attach.photo.owner_id}_{attach.photo.id}")
            elif attach.doc:
                attachments.append(f"doc{attach.doc.owner_id}_{attach.doc.id}")
            elif attach.video:
                attachments.append(f"video{attach.video.owner_id}_{attach.video.id}")

    text_content = message.text.strip() if message.text else "Без текста"
    stars = "⭐️" * rating

    full_text = (
        f"Отзыв #{order_id}\n"
        f"Клиент: {first_name}\n"
        f"Город: {city}\n"
        f"Оценка: {stars}\n"
        f"Отзыв: {text_content}"
    )

    try:
        attach_str = ",".join(attachments)

        await bot.api.messages.send(
            peer_id=REVIEWS_CHAT_ID,
            message=full_text,
            attachment=attach_str,
            random_id=0
        )
        await message.answer("Большое спасибо за ваш отзыв! ❤️ Он успешно опубликован.", keyboard=main_kb)
    except Exception as e:
        logging.error(f"Ошибка при публикации отзыва в канал: {e}")
        await message.answer("Спасибо за ваш отзыв! ❤️", keyboard=main_kb)

    await bot.state_dispenser.delete(message.peer_id)