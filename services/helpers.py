# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
import asyncio
import logging
import os
from datetime import datetime, timezone, timedelta

import aiohttp

from env.config import bot
from states.FSM import OrderForm


def is_night_time():
    now_utc = datetime.now(timezone.utc)
    now_msk = now_utc + timedelta(hours=3)
    return now_msk.hour < 9 or now_msk.hour > 20


def get_admins():
    admin_ids_str = os.environ.get("ADMIN_ID", "")
    return [int(x.strip()) for x in admin_ids_str.split(",") if x.strip().isdigit()]


async def decode_vin(vin: str):
    """Декодирование VIN через бесплатное API NHTSA."""
    url = f"https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVin/{vin}?format=json"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                data = await response.json()
                results = data.get("Results", [])

                make = next((item['Value'] for item in results if item['Variable'] == 'Make' and item['Value']), None)
                model = next((item['Value'] for item in results if item['Variable'] == 'Model' and item['Value']), None)
                year = next((item['Value'] for item in results if item['Variable'] == 'Model Year' and item['Value']),
                            "")

                if make and model:
                    return f"{make} {model} {year}".strip().title()
                return None
    except Exception as e:
        logging.error(f"Ошибка декодирования VIN через API: {e}")
        return None


# Убедись, что импортируешь bot из main.py
async def abandoned_cart_timer(peer_id: int):
    await asyncio.sleep(1800) # 30 минут

    # Проверяем, есть ли всё еще активный стейт у пользователя
    state_data = await bot.state_dispenser.get(peer_id)

    if state_data and state_data.state:
        text = (
            "⏳ Вы начали оформлять заказ, но не завершили его!\n\n"
            "Если у вас возникли сложности, наш менеджер готов помочь.\n"
            "Вы можете продолжить оформление прямо сейчас, ответив на предыдущее сообщение бота."
        )
        try:
            await bot.api.messages.send(peer_id=peer_id, message=text, random_id=0)
        except Exception:
            pass