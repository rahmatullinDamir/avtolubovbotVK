from vkbottle import BaseStateGroup

class OrderForm(BaseStateGroup):
    waiting_for_vin = "waiting_for_vin"
    waiting_for_car_info_edit = "waiting_for_car_info_edit"
    waiting_for_details = "waiting_for_details"
    waiting_for_city = "waiting_for_city"
    waiting_for_contact = "waiting_for_contact"
    waiting_for_manager = "waiting_for_manager"
    waiting_for_confirmation = "waiting_for_confirmation"

class ReviewForm(BaseStateGroup):
    waiting_for_review = "waiting_for_review"

class AdminForm(BaseStateGroup):
    waiting_for_broadcast = "waiting_for_broadcast"