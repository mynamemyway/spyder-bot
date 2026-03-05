# tests/test_keyboards.py

from aiogram.types import InlineKeyboardMarkup

from app.keyboards import (
    CatalogCallback,
    ActionCallback,
    get_start_keyboard,
    get_catalog_keyboard,
    get_banner_materials_keyboard,
    get_print_quality_keyboard,
    get_quantity_keyboard,
    get_urgency_keyboard,
    get_delivery_keyboard,
    get_order_keyboard,
    get_manager_contact_keyboard,
    get_back_button_keyboard,
    get_help_keyboard,
    get_processing_type_keyboard,
)
from app.config import settings


def test_get_start_keyboard():
    """Тестирует клавиатуру для стартового сообщения."""
    keyboard = get_start_keyboard()
    assert isinstance(keyboard, InlineKeyboardMarkup)
    button = keyboard.inline_keyboard[0][0]
    assert button.text == "🗂️ Каталог"
    assert button.callback_data == CatalogCallback(level=1, action="products").pack()


def test_get_catalog_keyboard():
    """Тестирует клавиатуру для выбора категории продукта."""
    keyboard = get_catalog_keyboard()
    assert isinstance(keyboard, InlineKeyboardMarkup)
    assert len(keyboard.inline_keyboard) == 2
    assert keyboard.inline_keyboard[0][0].text == "Баннеры"
    assert keyboard.inline_keyboard[0][0].callback_data == CatalogCallback(level=2, action="banners").pack()
    assert keyboard.inline_keyboard[1][0].text == "⬅️ Назад"
    assert keyboard.inline_keyboard[1][0].callback_data == CatalogCallback(level=0, action="back_to_start").pack()


def test_get_banner_materials_keyboard():
    """Тестирует клавиатуру для выбора материалов баннера."""
    keyboard = get_banner_materials_keyboard()
    assert isinstance(keyboard, InlineKeyboardMarkup)
    # Проверяем наличие одной из кнопок и кнопки "Назад"
    assert keyboard.inline_keyboard[0][0].text == "Стандартный, 440 г/м²"
    assert keyboard.inline_keyboard[0][0].callback_data == CatalogCallback(level=3, action="select_material", item_id="frontlit_440").pack()
    assert keyboard.inline_keyboard[-1][0].text == "⬅️ Назад"
    assert keyboard.inline_keyboard[-1][0].callback_data == CatalogCallback(level=1, action="back_to_products").pack()


def test_get_print_quality_keyboard():
    """Тестирует клавиатуру для выбора качества печати."""
    keyboard = get_print_quality_keyboard()
    assert isinstance(keyboard, InlineKeyboardMarkup)
    assert keyboard.inline_keyboard[1][0].text == "720 dpi — Стандарт"
    assert keyboard.inline_keyboard[1][0].callback_data == CatalogCallback(level=4, action="select_quality", item_id="720").pack()
    assert keyboard.inline_keyboard[-1][0].callback_data == CatalogCallback(level=3, action="back_to_material_input").pack()


def test_get_help_keyboard():
    """Тестирует клавиатуру для меню помощи."""
    keyboard = get_help_keyboard()
    assert isinstance(keyboard, InlineKeyboardMarkup)
    buttons = {btn.text: btn for row in keyboard.inline_keyboard for btn in row}

    assert "📲 Наш телеграм" in buttons
    assert buttons["📲 Наш телеграм"].url == settings.MANAGER_TELEGRAM_URL
    assert "🗑️ Очистить историю" in buttons
    assert buttons["🗑️ Очистить историю"].callback_data == ActionCallback(name="reset").pack()
    assert "🔄 Перезапустить бота" in buttons
    assert buttons["🔄 Перезапустить бота"].callback_data == ActionCallback(name="restart").pack()


def test_get_quantity_keyboard():
    """Тестирует клавиатуру для выбора количества."""
    keyboard = get_quantity_keyboard()
    assert isinstance(keyboard, InlineKeyboardMarkup)
    assert keyboard.inline_keyboard[0][0].text == "1 шт."
    assert keyboard.inline_keyboard[0][0].callback_data == CatalogCallback(level=6, action="select_quantity", item_id="1").pack()
    assert keyboard.inline_keyboard[1][0].text == "Другое количество"
    assert keyboard.inline_keyboard[1][0].callback_data == CatalogCallback(level=6, action="enter_quantity").pack()
    assert keyboard.inline_keyboard[2][0].text == "⬅️ Назад"
    assert keyboard.inline_keyboard[2][0].callback_data == CatalogCallback(level=5, action="back_to_processing_selection").pack()


def test_get_urgency_keyboard():
    """Тестирует клавиатуру для выбора срочности."""
    keyboard = get_urgency_keyboard()
    assert isinstance(keyboard, InlineKeyboardMarkup)
    assert keyboard.inline_keyboard[0][0].text == "Обычный (2-3 дня)"
    assert keyboard.inline_keyboard[0][0].callback_data == CatalogCallback(level=7, action="select_urgency", item_id="regular").pack()
    assert keyboard.inline_keyboard[1][0].text == "Срочный (1 день)"
    assert keyboard.inline_keyboard[1][0].callback_data == CatalogCallback(level=7, action="select_urgency", item_id="urgent").pack()
    assert keyboard.inline_keyboard[2][0].callback_data == CatalogCallback(level=6, action="back_to_quantity_selection").pack()


def test_get_delivery_keyboard():
    """Тестирует клавиатуру для выбора способа доставки."""
    keyboard = get_delivery_keyboard()
    assert isinstance(keyboard, InlineKeyboardMarkup)
    assert keyboard.inline_keyboard[0][0].text == "Самовывоз"
    assert keyboard.inline_keyboard[0][0].callback_data == CatalogCallback(level=8, action="select_delivery", item_id="no").pack()
    assert keyboard.inline_keyboard[1][0].text == "Доставка (350р.)"
    assert keyboard.inline_keyboard[1][0].callback_data == CatalogCallback(level=8, action="select_delivery", item_id="yes").pack()
    assert keyboard.inline_keyboard[2][0].callback_data == CatalogCallback(level=7, action="back_to_urgency_selection").pack()


def test_get_order_keyboard():
    """Тестирует клавиатуру для подтверждения заказа."""
    keyboard = get_order_keyboard()
    assert isinstance(keyboard, InlineKeyboardMarkup)
    assert keyboard.inline_keyboard[0][0].text == "🚀 Подтвердить заказ"
    assert keyboard.inline_keyboard[0][0].callback_data == CatalogCallback(level=9, action="confirm_order").pack()
    assert keyboard.inline_keyboard[1][0].callback_data == CatalogCallback(level=8, action="back_to_delivery_selection").pack()


def test_get_manager_contact_keyboard():
    """Тестирует клавиатуру для связи с менеджером."""
    keyboard = get_manager_contact_keyboard()
    assert isinstance(keyboard, InlineKeyboardMarkup)
    button = keyboard.inline_keyboard[0][0]
    assert button.text == "Связаться с менеджером"
    assert button.url == settings.MANAGER_TELEGRAM_URL


def test_get_back_button_keyboard():
    """Тестирует клавиатуру с единственной кнопкой 'Назад'."""
    keyboard = get_back_button_keyboard(return_level=2, return_action="test_action")
    assert isinstance(keyboard, InlineKeyboardMarkup)
    button = keyboard.inline_keyboard[0][0]
    assert button.text == "⬅️ Назад"
    assert button.callback_data == CatalogCallback(level=2, action="test_action").pack()


def test_get_processing_type_keyboard():
    """Тестирует клавиатуру для выбора типа обработки."""
    keyboard = get_processing_type_keyboard()
    assert isinstance(keyboard, InlineKeyboardMarkup)
    assert keyboard.inline_keyboard[0][0].text == "Установка люверсов"
    assert keyboard.inline_keyboard[0][0].callback_data == CatalogCallback(level=5, action="select_processing", item_id="grommets").pack()
    assert keyboard.inline_keyboard[-1][0].callback_data == CatalogCallback(level=4, action="back_to_quality_selection").pack()