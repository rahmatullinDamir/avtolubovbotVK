from vkbottle import Keyboard, KeyboardButtonColor, Text

# --- ОСНОВНЫЕ КЛАВИАТУРЫ ---
main_kb = Keyboard(one_time=False)
main_kb.add(Text("🚗 Новый заказ"), color=KeyboardButtonColor.POSITIVE)
main_kb.add(Text("🔍 Мои заказы"), color=KeyboardButtonColor.PRIMARY)
main_kb.row()
main_kb.add(Text("🚚 Доставка и оплата"), color=KeyboardButtonColor.SECONDARY)
main_kb.add(Text("📍 Наши контакты"), color=KeyboardButtonColor.SECONDARY)
main_kb = main_kb.get_json()

cancel_kb = Keyboard(one_time=False)
cancel_kb.add(Text("❌ Отменить заказ"), color=KeyboardButtonColor.NEGATIVE)
cancel_kb = cancel_kb.get_json()

contact_and_cancel_kb = Keyboard(one_time=False)
# В ВК нет "отправить контакт", пользователь должен ввести его сам или мы просим его текстом
contact_and_cancel_kb.add(Text("❌ Отменить заказ"), color=KeyboardButtonColor.NEGATIVE)
contact_and_cancel_kb = contact_and_cancel_kb.get_json()

confirm_kb = Keyboard(one_time=False)
confirm_kb.add(Text("✅ Всё верно, отправить"), color=KeyboardButtonColor.POSITIVE)
confirm_kb.row()
confirm_kb.add(Text("✏️ Заполнить заново"), color=KeyboardButtonColor.PRIMARY)
confirm_kb.add(Text("❌ Отменить заказ"), color=KeyboardButtonColor.NEGATIVE)
confirm_kb = confirm_kb.get_json()

manager_kb = Keyboard(one_time=False)
manager_kb.add(Text("👨‍💻 Менеджер Радик"), color=KeyboardButtonColor.PRIMARY)
manager_kb.add(Text("👨‍💻 Менеджер Никита"), color=KeyboardButtonColor.PRIMARY)
manager_kb.row()
manager_kb.add(Text("🎲 Любой менеджер"), color=KeyboardButtonColor.SECONDARY)
manager_kb = manager_kb.get_json()

# --- INLINE КЛАВИАТУРЫ ---
process_vin_kb = Keyboard(inline=True)
process_vin_kb.add(Text("✅ Да, всё верно", payload={"cmd": "vin_correct"}), color=KeyboardButtonColor.POSITIVE)
process_vin_kb.row()
process_vin_kb.add(Text("✏️ Нет, изменить данные", payload={"cmd": "vin_manual"}), color=KeyboardButtonColor.PRIMARY)
process_vin_kb = process_vin_kb.get_json()

skip_kb = Keyboard(inline=True)
skip_kb.add(Text("Пропустить ➡️", payload={"cmd": "skip_review"}), color=KeyboardButtonColor.SECONDARY)
skip_kb = skip_kb.get_json()

role_kb = Keyboard(inline=True)
role_kb.add(Text("👤 Физическое лицо", payload={"role": "person"}), color=KeyboardButtonColor.PRIMARY)
role_kb.row()
role_kb.add(Text("🏢 Юридическое лицо", payload={"role": "company"}), color=KeyboardButtonColor.SECONDARY)
role_kb = role_kb.get_json()

def create_nps_kb(order_id) -> str:
    kb = Keyboard(inline=True)
    for i in range(1, 6):
        kb.add(Text(f"{i} ⭐️", payload={"nps": i, "order_id": order_id}),
               color=KeyboardButtonColor.SECONDARY if i < 4 else KeyboardButtonColor.POSITIVE)
        if i == 3: kb.row() # Перенос строки после 3 звезд
    return kb.get_json()