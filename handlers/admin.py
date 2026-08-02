import asyncio
import os
from datetime import datetime

from vkbottle.bot import Message
from env.config import bot
from env.config import MSK
from services.helpers import get_admins
from keyboards.keyboards import main_kb
from services.google_sheet import get_sheets_client, get_all_user_ids
from states.FSM import AdminForm


# Статистика. Ловим команды /stats или !stats
@bot.on.message(text=["/stats", "!stats"])
async def admin_stats(message: Message):
    if message.from_id not in get_admins():
        return

    loading = await message.answer("Собираю статистику... ⏳")

    # Делаем запрос к Google Таблицам асинхронно, чтобы не "вешать" бота
    def fetch_stats():
        gc = get_sheets_client()
        sh = gc.open_by_url(os.environ.get("GOOGLE_SHEET_URL"))
        return sh.sheet1.get_all_values()[1:]

    rows = await asyncio.to_thread(fetch_stats)

    today = datetime.now(MSK).strftime("%Y-%m-%d")
    today_count = len([r for r in rows if r[0].startswith(today)])

    # Убрали Markdown, так как ВК его не поддерживает
    text = (
        f"📊 Статистика:\n\n"
        f"• Заявок сегодня: {today_count}\n"
        f"• Всего клиентов: {len(set(r[2] for r in rows if len(r) > 2))}\n"
        f"• Всего заказов: {len(rows)}"
    )
    await message.answer(text)


# Запуск рассылки
@bot.on.message(text=["/mailing", "!mailing"], state="*")
async def mailing_start(message: Message):
    if message.from_id not in get_admins():
        return

    await message.answer("📢 Отправьте пост для рассылки (можно с фото/видео) или напишите /cancel для отмены.")
    await bot.state_dispenser.set(message.peer_id, AdminForm.waiting_for_broadcast)


# Отмена рассылки
@bot.on.message(text="/cancel", state=AdminForm.waiting_for_broadcast)
async def cancel_mailing(message: Message):
    await bot.state_dispenser.delete(message.peer_id)
    await message.answer("Рассылка отменена 🚫", keyboard=main_kb)


# Выполнение рассылки
@bot.on.message(state=AdminForm.waiting_for_broadcast)
async def mailing_exec(message: Message):
    if message.from_id not in get_admins():
        return

    uids = await asyncio.to_thread(get_all_user_ids)
    await message.answer(f"🚀 Начинаю рассылку на {len(uids)} чел...")

    # Собираем все медиафайлы, прикрепленные к посту рассылки
    attachments = []
    if message.attachments:
        for attach in message.attachments:
            if attach.photo:
                attachments.append(f"photo{attach.photo.owner_id}_{attach.photo.id}")
            elif attach.doc:
                attachments.append(f"doc{attach.doc.owner_id}_{attach.doc.id}")
            elif attach.video:
                attachments.append(f"video{attach.video.owner_id}_{attach.video.id}")

    attach_str = ",".join(attachments)
    text_content = message.text if message.text else ""

    success_count = 0
    for uid in uids:
        try:
            # В ВК собираем сообщение "вручную" из текста и вложений
            await bot.api.messages.send(
                peer_id=uid,
                message=text_content,
                attachment=attach_str,
                random_id=0
            )
            success_count += 1
            await asyncio.sleep(0.05)  # Задержка для обхода лимитов API ВК
        except Exception:
            pass  # Игнорируем ошибки (например, если человек запретил боту писать)

    await message.answer(f"✅ Готово! Успешно доставлено: {success_count}/{len(uids)}", keyboard=main_kb)
    await bot.state_dispenser.delete(message.peer_id)