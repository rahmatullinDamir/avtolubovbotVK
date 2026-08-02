# --- ФУНКЦИИ ДЛЯ GOOGLE ТАБЛИЦ ---
import json
import logging
import os
import asyncio
import re
from datetime import datetime

import gspread

from env.config import MSK, MANAGER_CHAT_ID, bot
from keyboards.keyboards import create_nps_kb


def get_sheets_client():
    creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
    creds_dict = json.loads(creds_json)
    return gspread.service_account_from_dict(creds_dict)


def export_to_google_sheet(row_data):
    try:
        gc = get_sheets_client()
        sh = gc.open_by_url(os.environ.get("GOOGLE_SHEET_URL"))
        worksheet = sh.sheet1
        orders = worksheet.get_all_values()
        order_id = len(orders)
        row_data.insert(1, f"{order_id}")
        worksheet.append_row(row_data)
        return order_id
    except Exception as e:
        logging.error(f"Ошибка Sheets Export: {e}")
        return "Ошибка"


def get_user_orders(user_id):
    try:
        gc = get_sheets_client()
        sh = gc.open_by_url(os.environ.get("GOOGLE_SHEET_URL"))
        worksheet = sh.sheet1
        all_rows = worksheet.get_all_values()[1:]
        user_orders = [row for row in all_rows if row[2] == str(user_id)]
        return user_orders[-5:]
    except Exception as e:
        logging.error(f"Ошибка получения заказов: {e}")
        return []


def get_cached_car_info(vin_to_search):
    """Поиск VIN в истории таблицы для использования ручных исправлений."""
    try:
        gc = get_sheets_client()
        sh = gc.open_by_url(os.environ.get("GOOGLE_SHEET_URL"))
        worksheet = sh.sheet1
        all_rows = worksheet.get_all_values()[1:]

        for row in reversed(all_rows):
            if len(row) > 9 and row[8] == vin_to_search:
                car_info = row[9]
                if car_info and car_info not in ["Не определено", "Неизвестно", "Не удалось определить"]:
                    return car_info
        return None
    except Exception as e:
        logging.error(f"Ошибка поиска VIN в кэше таблицы: {e}")
        return None


def update_order_status(order_id_str, new_status):
    """Обновляет только статус заказа в Google Таблице и возвращает ID клиента"""
    try:
        gc = get_sheets_client()
        sh = gc.open_by_url(os.environ.get("GOOGLE_SHEET_URL"))
        worksheet_orders = sh.sheet1

        cell = worksheet_orders.find(order_id_str, in_column=2)  # Ищем в колонке B
        if cell:
            # Обновляем колонку L (Статус)
            worksheet_orders.update_cell(cell.row, 12, new_status)

            # Получаем ID клиента (Колонка C) для уведомления
            row_values = worksheet_orders.row_values(cell.row)
            return row_values[2]
        return None
    except Exception as e:
        logging.error(f"Ошибка обновления статуса: {e}")
        return None


def update_order_and_get_info(order_id_str, price_str, manager_name, supplier="", supplier_order="", delivery_rub=0):
    """Обновляет цену, статус, поставщика и записывает расчеты в лист Экономика"""
    try:
        gc = get_sheets_client()
        sh = gc.open_by_url(os.environ.get("GOOGLE_SHEET_URL"))

        # Подключаем обе вкладки
        worksheet_orders = sh.sheet1
        worksheet_economy = sh.worksheet("Экономика")

        cell = worksheet_orders.find(order_id_str, in_column=2)  # Ищем в колонке B

        if cell:
            row_values = worksheet_orders.row_values(cell.row)
            user_id = row_values[2]  # Колонка C (Telegram ID)

            # 1. ОБНОВЛЕНИЕ ОСНОВНОГО ЛИСТА "ЗАЯВКИ"
            worksheet_orders.update_cell(cell.row, 12, "Обработана ✅")
            worksheet_orders.update_cell(cell.row, 13, price_str)
            worksheet_orders.update_cell(cell.row, 7, manager_name)

            if supplier:
                worksheet_orders.update_cell(cell.row, 15, supplier)
            if supplier_order:
                worksheet_orders.update_cell(cell.row, 16, supplier_order)

            # 2. РАСЧЕТ И ЗАПИСЬ В ЛИСТ "ЭКОНОМИКА"
            try:
                price_val = float(price_str)
                date_now = datetime.now(MSK).strftime("%Y-%m-%d")

                # Высчитываем процент доставки (Доставка в руб. / Цена * 100)
                if price_val > 0 and delivery_rub > 0:
                    delivery_pct = (float(delivery_rub) / price_val) * 100
                    delivery_pct_str = f"{round(delivery_pct, 2)}%"
                else:
                    delivery_pct_str = "0%"

                # Формируем строку строго по твоим столбцам
                economy_row = [
                    order_id_str,  # 1: № заявки
                    manager_name,  # 2: Менеджер
                    price_val,  # 3: Цена
                    round(price_val * 0.08, 2),  # 4: Налоги и страховые (8%)
                    delivery_pct_str,  # 5: Доставка в % (ВЫСЧИТАНО АВТОМАТИЧЕСКИ)
                    round(price_val * 0.07, 2),  # 6: Чистая прибыль ИП (7%)
                    round(price_val * 0.05, 2),  # 7: Возвраты\брак (5%)
                    round(price_val * 0.10, 2),  # 8: Выработка менеджера (10%)
                    round(price_val * 0.35, 2),  # 9: Итоговая минимальная накрутка (35%)
                    date_now  # 10: Дата
                ]

                worksheet_economy.append_row(economy_row)

            except Exception as eco_err:
                logging.error(f"Ошибка при записи в Экономику: {eco_err}")

            update_manager_salary(manager_name)
            return user_id, manager_name
        return None, None
    except Exception as e:
        logging.error(f"Ошибка Update Sheets: {e}")
        return None, None


def update_manager_salary(manager_tag):
    """Считает выработку менеджера за текущий месяц и записывает в лист 'Выработка'"""
    try:
        gc = get_sheets_client()
        sh = gc.open_by_url(os.environ.get("GOOGLE_SHEET_URL"))

        worksheet_economy = sh.worksheet("Экономика")
        worksheet_salary = sh.worksheet("Выработка")

        name_mapping = {
            "@radga12": "Габдрафиков Радик",
            "@Samyydobryy853": "Кулаков Никита"
        }

        real_name = name_mapping.get(manager_tag, manager_tag)
        current_month = datetime.now(MSK).strftime("%Y-%m")
        economy_data = worksheet_economy.get_all_values()[1:]

        total_salary = 0.0

        for row in economy_data:
            if len(row) >= 10:
                row_manager = row[1]
                row_salary = row[7]
                row_date = row[9]

                if row_manager == manager_tag and row_date.startswith(current_month):
                    try:
                        salary_val = float(str(row_salary).replace(",", "."))
                        total_salary += salary_val
                    except ValueError:
                        pass

        cell = worksheet_salary.find(real_name, in_column=1)
        if cell:
            worksheet_salary.update_cell(cell.row, 2, round(total_salary, 2))
        else:
            logging.warning(f"Менеджер {real_name} не найден на листе 'Выработка'")

    except Exception as e:
        logging.error(f"Ошибка при подсчете зарплаты: {e}")


def get_all_user_ids():
    try:
        gc = get_sheets_client()
        sh = gc.open_by_url(os.environ.get("GOOGLE_SHEET_URL"))
        worksheet = sh.sheet1
        return list(set([int(uid) for uid in worksheet.col_values(3)[1:] if uid.isdigit()]))
    except Exception:
        return []


def update_supplier_number_only(order_id: str, supplier_order: str) -> bool:
    """Обновляет ТОЛЬКО номер заказа у поставщика (колонка 16) для указанной заявки."""
    try:
        gc = get_sheets_client()
        sh = gc.open_by_url(os.environ.get("GOOGLE_SHEET_URL"))
        worksheet_orders = sh.sheet1

        # Ищем заявку в колонке B (2)
        cell = worksheet_orders.find(order_id, in_column=2)

        if cell:
            # Записываем номер поставщика в 16-ю колонку
            worksheet_orders.update_cell(cell.row, 16, supplier_order)
            return True
        return False
    except Exception as e:
        logging.error(f"Ошибка обновления номера поставщика в таблице: {e}")
        return False


def get_city_by_order_id(order_id_str):
    """Ищет заявку по номеру и возвращает город клиента"""
    try:
        gc = get_sheets_client()
        sh = gc.open_by_url(os.environ.get("GOOGLE_SHEET_URL"))
        worksheet_orders = sh.sheet1

        # Ищем номер заказа в колонке B (2-я колонка)
        cell = worksheet_orders.find(str(order_id_str), in_column=2)

        if cell:
            row_values = worksheet_orders.row_values(cell.row)

            # ⚠️ ВНИМАНИЕ: Укажи индекс колонки, в которой у тебя хранится город!
            # В Python нумерация начинается с 0.
            # Например: если город в колонке I (9-я по счету), то индекс будет 8.
            # Если город в колонке J (10-я), индекс будет 9.
            city_index = 7  # <--- ЗАМЕНИ НА СВОЙ ИНДЕКС КОЛОНКИ С ГОРОДОМ

            if len(row_values) > city_index:
                city = row_values[city_index]
                return city if city else "Не указан"

        return "Не указан"
    except Exception as e:
        logging.error(f"Ошибка получения города для заявки {order_id_str}: {e}")
        return "Не указан"