import os
from datetime import timezone, timedelta

# Импортируем Bot из библиотеки для ВК
from vkbottle.bot import Bot

# --- НАСТРОЙКИ ---
VK_TOKEN = os.environ.get("VK_TOKEN")

# Обязательно оборачиваем в int(), так как ВК требует числа!
# Для подстраховки можно оставить твои ID по умолчанию на случай локальных тестов
MANAGER_CHAT_ID = int(os.environ.get("MANAGER_CHAT_ID", 2000000340))
REVIEWS_CHAT_ID = int(os.environ.get("REVIEWS_CHAT_ID", 2000000341))

# Глобальная настройка Московского времени (UTC+3)
MSK = timezone(timedelta(hours=3))

# Инициализируем бота VKBottle
bot = Bot(token=VK_TOKEN)