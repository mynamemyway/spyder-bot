# app/keyboards.py

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.config import settings


class CatalogCallback(CallbackData, prefix="catalog"):
    """
    CallbackData factory for catalog navigation buttons.

    Attributes:
        level (int): The current level in the sales funnel (0: start, 1: products, 2: materials, etc.).
        action (str): The specific action or choice (e.g., 'banners', 'frontlit', 'back').
        item_id (str | None): An optional identifier for the selected item.
    """
    level: int
    action: str
    item_id: str | None = None


class ActionCallback(CallbackData, prefix="action"):
    """
    CallbackData factory for general action buttons (e.g., in the help menu).

    Attributes:
        name (str): The name of the action to perform (e.g., 'restart', 'reset').
    """
    name: str



def get_start_keyboard() -> InlineKeyboardMarkup:
    """
    Builds the keyboard for the start message with a "Catalog" button.
    """
    builder = InlineKeyboardBuilder()
    builder.button(
        text="🗂️ Каталог",
        callback_data=CatalogCallback(level=1, action="products").pack()
    )
    return builder.as_markup()


def get_catalog_keyboard() -> InlineKeyboardMarkup:
    """
    Builds the keyboard for product category selection.
    For the MVP, it only contains "Banners".
    """
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Баннеры",
        callback_data=CatalogCallback(level=2, action="banners").pack()
    )
    builder.button(
        text="⬅️ Назад",
        callback_data=CatalogCallback(level=0, action="back_to_start").pack()
    )
    builder.adjust(1)
    return builder.as_markup()


def get_banner_materials_keyboard() -> InlineKeyboardMarkup:
    """
    Builds the keyboard for banner material selection.
    """
    builder = InlineKeyboardBuilder()
    # Buttons are created based on the price list from calculator_from_website_banners.md
    # The item_id corresponds to the internal identifiers we will use in the pricing logic.
    builder.button(
        text="Стандартный, 440 г/м²",
        callback_data=CatalogCallback(level=3, action="select_material", item_id="frontlit_440").pack()
    )
    builder.button(
        text="Усиленный, 530 г/м²",
        callback_data=CatalogCallback(level=3, action="select_material", item_id="frontlit_cast_530").pack()
    )
    builder.button(
        text="Непрозрачный (Blackout)",
        callback_data=CatalogCallback(level=3, action="select_material", item_id="blackout").pack()
    )
    builder.button(
        text="Транслюцентный (Backlit)",
        callback_data=CatalogCallback(level=3, action="select_material", item_id="backlit").pack()
    )
    builder.button(
        text="Сетка баннерная (Mesh)",
        callback_data=CatalogCallback(level=3, action="select_material", item_id="mesh").pack()
    )
    builder.button(
        text="⬅️ Назад",
        callback_data=CatalogCallback(level=1, action="back_to_products").pack()
    )
    builder.adjust(1)
    return builder.as_markup()


def get_print_quality_keyboard() -> InlineKeyboardMarkup:
    """
    Builds the keyboard for print quality (DPI) selection.
    """
    builder = InlineKeyboardBuilder()
    builder.button(
        text="540 dpi — Эконом",
        callback_data=CatalogCallback(level=4, action="select_quality", item_id="540").pack()
    )
    builder.button(
        text="720 dpi — Стандарт",
        callback_data=CatalogCallback(level=4, action="select_quality", item_id="720").pack()
    )
    builder.button(
        text="1440 dpi — Интерьерное",
        callback_data=CatalogCallback(level=4, action="select_quality", item_id="1440").pack()
    )
    builder.button(
        text="⬅️ Назад",
        callback_data=CatalogCallback(level=3, action="back_to_material_input").pack()
    )
    builder.adjust(1)
    return builder.as_markup()


def get_urgency_keyboard() -> InlineKeyboardMarkup:
    """
    Builds the keyboard for order urgency selection.
    """
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Обычный (2-3 дня)",
        callback_data=CatalogCallback(level=7, action="select_urgency", item_id="regular").pack()
    )
    builder.button(
        text="Срочный (1 день)",
        callback_data=CatalogCallback(level=7, action="select_urgency", item_id="urgent").pack()
    )
    builder.button(
        text="⬅️ Назад",
        callback_data=CatalogCallback(level=6, action="back_to_quantity_selection").pack()
    )
    builder.adjust(1)
    return builder.as_markup()


def get_delivery_keyboard() -> InlineKeyboardMarkup:
    """
    Builds the keyboard for delivery selection.
    """
    builder = InlineKeyboardBuilder()
    builder.button(text="Самовывоз", callback_data=CatalogCallback(level=8, action="select_delivery", item_id="no").pack())
    builder.button(text="Доставка (350р.)", callback_data=CatalogCallback(level=8, action="select_delivery", item_id="yes").pack())
    builder.button(
        text="⬅️ Назад",
        callback_data=CatalogCallback(level=7, action="back_to_urgency_selection").pack()
    )
    builder.adjust(1)
    return builder.as_markup()


def get_processing_type_keyboard() -> InlineKeyboardMarkup:
    """
    Builds the keyboard for post-processing type selection.
    """
    builder = InlineKeyboardBuilder()
    builder.button(text="Установка люверсов", callback_data=CatalogCallback(level=5, action="select_processing", item_id="grommets").pack())
    builder.button(text="Проварка карманов", callback_data=CatalogCallback(level=5, action="select_processing", item_id="pockets").pack())
    builder.button(text="Проварка краёв без люверсов", callback_data=CatalogCallback(level=5, action="select_processing", item_id="welded_edges").pack())
    builder.button(text="Под обрез (без обработки)", callback_data=CatalogCallback(level=5, action="select_processing", item_id="cut_off").pack())
    builder.button(
        text="⬅️ Назад",
        callback_data=CatalogCallback(level=4, action="back_to_quality_selection").pack()
    )
    builder.adjust(1)
    return builder.as_markup()


def get_quantity_keyboard() -> InlineKeyboardMarkup:
    """
    Builds the keyboard for quantity selection.
    """
    builder = InlineKeyboardBuilder()
    builder.button(
        text="1 шт.",
        callback_data=CatalogCallback(level=6, action="select_quantity", item_id="1").pack()
    )
    builder.button(
        text="2 шт.",
        callback_data=CatalogCallback(level=6, action="select_quantity", item_id="2").pack()
    )
    builder.button(text="Другое количество", callback_data=CatalogCallback(level=6, action="enter_quantity").pack())
    builder.button(
        text="⬅️ Назад",
        callback_data=CatalogCallback(level=5, action="back_to_processing_selection").pack()
    )
    builder.adjust(2, 1, 1)
    return builder.as_markup()


def get_back_button_keyboard(return_level: int, return_action: str) -> InlineKeyboardMarkup:
    """
    Builds a simple keyboard with just a "Back" button.
    """
    builder = InlineKeyboardBuilder()
    builder.button(
        text="⬅️ Назад",
        callback_data=CatalogCallback(level=return_level, action=return_action).pack()
    )
    return builder.as_markup()


def get_help_keyboard() -> InlineKeyboardMarkup:
    """
    Builds the keyboard for the help message, providing quick access to common actions.
    """
    builder = InlineKeyboardBuilder()
    builder.button(
        text="📲 Наш телеграм",
        url=settings.MANAGER_TELEGRAM_URL
    )
    builder.button(
        text="⬅️ Главное меню",
        callback_data=ActionCallback(name="restart").pack()
    )
    builder.button(
        text="🗑️ Очистить историю",
        callback_data=ActionCallback(name="reset").pack()
    )
    builder.button(
        text="🔄 Перезапустить бота",
        callback_data=ActionCallback(name="restart").pack()
    )
    builder.adjust(2, 2)
    return builder.as_markup()


def get_order_keyboard() -> InlineKeyboardMarkup:
    """
    Builds a keyboard for the final order confirmation step.
    """
    builder = InlineKeyboardBuilder()
    builder.button(
        text="🚀 Подтвердить заказ",
        callback_data=CatalogCallback(level=9, action="confirm_order").pack()
    )
    builder.button(
        text="⬅️ Назад",
        callback_data=CatalogCallback(level=8, action="back_to_delivery_selection").pack()
    )
    builder.adjust(1)
    return builder.as_markup()


def get_manager_contact_keyboard() -> InlineKeyboardMarkup:
    """
    Builds a keyboard with a single button to contact the manager.
    """
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Связаться с менеджером",
        url=settings.MANAGER_TELEGRAM_URL
    )
    return builder.as_markup()