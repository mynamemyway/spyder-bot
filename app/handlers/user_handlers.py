# app/handlers/user_handlers.py

import logging
from pathlib import Path
import re

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardMarkup, InputMediaPhoto, Message, User
from langchain_core.messages import AIMessage, HumanMessage

from app.config import settings
from app.core.chain import FallbackLoggingCallbackHandler, get_rag_chain
from app.core.memory import get_chat_memory
from app.core.pricing import calculate_price
from app.core.stats import log_query
from app.utils.text_formatters import escape_markdown_legacy, sanitize_for_telegram_markdown
from app.keyboards import (
    CatalogCallback,
    ActionCallback,
    get_help_keyboard,
    get_start_keyboard,
    get_catalog_keyboard,
    get_banner_materials_keyboard,
    get_back_button_keyboard,
    get_order_keyboard,
    get_print_quality_keyboard,
    get_urgency_keyboard,
    get_delivery_keyboard,
    get_processing_type_keyboard,
    get_quantity_keyboard,
    get_manager_contact_keyboard,
)

# Create a new Router instance for user-facing handlers.
router = Router()

# Define FSM states for the order process
class OrderState(StatesGroup):
    """States for the product ordering funnel."""
    entering_size = State()
    choosing_print_quality = State()
    choosing_quantity = State()
    entering_quantity = State()
    choosing_urgency = State()
    choosing_delivery = State()
    choosing_processing_type = State()
    entering_delivery_address = State()
    final_confirmation = State()
    entering_comment = State()


# Define the welcome message as a constant for reusability.
START_MESSAGE_TEXT = (
    "Добрый день!\nЯ — эксперт типографии 'Пиранья'!\n\n"
    "🫡 Готов помочь вам с выбором и заказом продукции, а также ответить на любые вопросы.\n\n"
    "Нажмите *Каталог*, чтобы начать, или просто задайте мне вопрос."
)

# Define static texts for different funnel steps
CATALOG_MESSAGE_TEXT = "Выберите категорию продукции:"
BANNERS_MESSAGE_TEXT = "Отлично, баннеры! Теперь давайте выберем подходящий материал. У каждого свои преимущества:"
MATERIAL_SELECTED_TEXT = (
    "Вы выбрали: *{material_name}*.\n\n"
    "Введите необходимый размер баннера цифрами в формате `Ширина x Высота` в метрах.\n"
    "Например:\n"
    "- `3 x 1.5`\n"
    "- `5 * 1,1`\n"
    "- `10 на 2`"
)

PROMPT_FOR_QUALITY_TEXT = (
    "🧮 **Ваш заказ**\n\n"
    "*- Материал:* {material_name}\n"
    "*- Размер:* {width} x {height} м\n\n"
    "👇 **Выберите качество печати:**"
)

PROMPT_FOR_PROCESSING_TEXT = (
    "🧮 **Ваш заказ**\n\n"
    "*- Материал:* {material_name}\n"
    "*- Размер:* {width} x {height} м\n"
    "*- Качество:* {quality} dpi\n\n"
    "👇 **Выберите тип обработки:**"
)

PROMPT_FOR_QUANTITY_TEXT = (
    "🧮 **Ваш заказ**\n\n"
    "*- Материал:* {material_name}\n"
    "*- Размер:* {width} x {height} м\n"
    "*- Качество:* {quality} dpi\n"
    "*- Обработка:* {processing}\n\n"
    "👇 **Выберите количество изделий:**"
)

PROMPT_FOR_MANUAL_QUANTITY_TEXT = (
    "🧮 **Ваш заказ**\n\n"
    "*- Материал:* {material_name}\n"
    "*- Размер:* {width} x {height} м\n"
    "*- Качество:* {quality} dpi\n"
    "*- Обработка:* {processing}\n\n"
    "👇 **Введите нужное количество цифрами:**"
)

PROMPT_FOR_URGENCY_TEXT = (
    "🧮 **Ваш заказ**\n\n"
    "*- Материал:* {material_name}\n"
    "*- Размер:* {width} x {height} м\n"
    "*- Качество:* {quality} dpi\n"
    "*- Обработка:* {processing}\n\n"
    "*- Количество:* {quantity} шт.\n\n"
    "👇 **Выберите срочность заказа:**"
)

PROMPT_FOR_DELIVERY_TEXT = (
    "🧮 **Ваш заказ**\n\n"
    "*- Материал:* {material_name}\n"
    "*- Размер:* {width} x {height} м\n"
    "*- Качество:* {quality} dpi\n"
    "*- Обработка:* {processing}\n\n"
    "*- Количество:* {quantity} шт.\n"
    "*- Срочность:* {urgency}\n\n"
    "👇 **Выберите способ получения:**"
)

FINAL_CALCULATION_TEXT = (
    "📦 **Ваш заказ рассчитан**\n\n"
    "*- Материал:* {material_name}\n"
    "*- Размер:* {width} x {height} м\n"
    "*- Качество:* {quality} dpi\n"
    "*- Обработка:* {processing}\n\n"
    "*- Количество:* {quantity} шт.\n"
    "*- Срочность:* {urgency}\n"
    "*- Получение:* {delivery_method}\n\n"
    "✅ **Итого:** {price:.2f} руб.\n\n"
)

ORDER_CONFIRMED_TEXT = (
    "🎉 **Ваш заказ принят!**\n\n"
    "*- Материал:* {material_name}\n"
    "*- Размер:* {width} x {height} м\n"
    "*- Качество:* {quality} dpi\n"
    "*- Обработка:* {processing}\n\n"
    "*- Количество:* {quantity} шт.\n"
    "*- Срочность:* {urgency}\n"
    "*- Получение:* {delivery_method}\n\n"
    "✅ **Итого:** {price:.2f} руб.\n\n"
    "🫡 Наш менеджер свяжется с вами в ближайшее время!"
)

MANAGER_ORDER_NOTIFICATION_TEXT = (
    "🔔 **Новый заказ от @{username}**\n\n"
    "*- Материал:* {material_name}\n"
    "*- Размер:* {width} x {height} м\n"
    "*- Качество:* {quality} dpi\n"
    "*- Обработка:* {processing}\n\n"
    "*- Количество:* {quantity} шт.\n"
    "*- Срочность:* {urgency}\n"
    "*- Получение:* {delivery_method}\n\n"
    "🤑 **Итого:** {price:.2f} руб."
) 

# A centralized mapping of material IDs to their human-readable names.
# This avoids duplication and ensures consistency across handlers.
MATERIAL_NAME_MAP = {
    "frontlit_440": "Стандартный, 440 г/м²",
    "frontlit_cast_530": "Усиленный/литой, 530 г/м²",
    "blackout": "Непрозрачный (Blackout)",
    "backlit": "Транслюцентный (Backlit)",
    "mesh": "Сетка баннерная (Mesh)",
}
# Define the static text for the "/help" command.
HELP_MESSAGE_TEXT = (
    "**🫂 Возможные Проблемы и Решения:**\n\n"
    "1. Ответ ИИ может занять 5-10 секунд. Пожалуйста, подождите.\n"
    "2. Если бот не отвечает, попробуйте перезапустить командой: /start\n"
    "3. Если AI сбился с темы, используйте команду /reset, чтобы очистить историю чата.\n\n"
    "**🗣 Прямая Связь:**\n"
    "Если вы хотите такого бота, "
    "напишите мне в telegram: @mynamemyway"
)

# Define the confirmation text for the /reset command.
RESET_CONFIRMATION_TEXT = (
    "🧹 История диалога успешно очищена."
)



@router.message(CommandStart())
async def handle_start(message: Message, state: FSMContext, bot: Bot):
    """
    Handles the /start command.
    Sends a welcome message and creates/updates the main "widget" message for this chat.
    """
    await log_query(
        user_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
        query_text="COMMAND: /start",
    )

    # --- Delete the previous calculator widget if it exists ---
    user_data = await state.get_data()
    old_message_id = user_data.get("calculator_message_id")
    if old_message_id:
        try:
            await bot.delete_message(chat_id=message.chat.id, message_id=old_message_id)
        except TelegramBadRequest as e:
            # Ignore if the message is already deleted or not found
            if "message to delete not found" not in str(e):
                logging.warning(f"Could not delete old calculator message {old_message_id}: {e}")

    photo_path = settings.WELCOME_PHOTO_PATH
    # Check if a welcome photo path is configured and the file exists.
    if photo_path and Path(photo_path).is_file():
        photo = FSInputFile(photo_path)
        widget_message = await message.answer_photo(
            photo=photo, caption=START_MESSAGE_TEXT, reply_markup=get_start_keyboard()
        )
    else:
        # If the path is set but the file is not found, log a warning.
        if photo_path:
            logging.warning(
                f"Welcome photo file not found at the specified path: {photo_path}"
            )
        widget_message = await message.answer(START_MESSAGE_TEXT, reply_markup=get_start_keyboard())

    await _pin_message_and_delete_notification(bot, widget_message.chat.id, widget_message.message_id)
    # IMPORTANT: Save the new message ID to the state, making it the current "live calculator".
    await state.clear() # Clear previous funnel state if any
    await state.update_data(calculator_message_id=widget_message.message_id, has_photo=bool(widget_message.photo))


@router.message(Command("help"))
async def handle_help(message: Message):
    """Handles the /help command, sending an informational message with a photo (if configured)."""
    await log_query(
        user_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
        query_text="COMMAND: /help",
    )
    photo_path = settings.HELP_PHOTO_PATH
    # Check if a help photo path is configured and the file exists.
    if photo_path and Path(photo_path).is_file():
        photo = FSInputFile(photo_path)
        await message.answer_photo(
            photo=photo, caption=HELP_MESSAGE_TEXT, reply_markup=get_help_keyboard()
        )
    else:
        # If the path is set but the file is not found, log a warning.
        if photo_path:
            logging.warning(
                f"Help photo file not found at the specified path: {photo_path}"
            )
        await message.answer(HELP_MESSAGE_TEXT, reply_markup=get_help_keyboard())


@router.message(Command("catalog"))
async def handle_catalog(message: Message, state: FSMContext, bot: Bot):
    """Handles the /catalog command, initiating the sales funnel and creating the calculator message."""
    await log_query(
        user_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
        query_text="COMMAND: /catalog",
    )

    # --- Delete the previous calculator widget if it exists ---
    user_data = await state.get_data()
    old_message_id = user_data.get("calculator_message_id")
    if old_message_id:
        try:
            await bot.delete_message(chat_id=message.chat.id, message_id=old_message_id)
        except TelegramBadRequest as e:
            # Ignore if the message is already deleted or not found
            if "message to delete not found" not in str(e):
                logging.warning(f"Could not delete old calculator message {old_message_id}: {e}")

    photo_path = settings.CATALOG_PHOTO_PATH
    # Check if a catalog photo path is configured and the file exists.
    if photo_path and Path(photo_path).is_file():
        photo = FSInputFile(photo_path)
        calculator_message = await message.answer_photo(
            photo=photo, caption=CATALOG_MESSAGE_TEXT, reply_markup=get_catalog_keyboard()
        )
    else:
        # If the path is set but the file is not found, log a warning.
        if photo_path:
            logging.warning(
                f"Catalog photo file not found at the specified path: {photo_path}"
            )
        calculator_message = await message.answer(CATALOG_MESSAGE_TEXT, reply_markup=get_catalog_keyboard())
    
    await _pin_message_and_delete_notification(bot, calculator_message.chat.id, calculator_message.message_id)
    await state.clear() # Clear previous funnel state if any
    # Save the ID of the calculator message to the state to be able to edit it later.
    # Also save whether it has a photo to simplify editing logic later.
    await state.update_data(calculator_message_id=calculator_message.message_id, has_photo=bool(calculator_message.photo))



@router.message(Command("reset"))
async def handle_reset(message: Message):
    """ 
    Handles the /reset command by clearing the user's chat history.
    """
    await log_query(
        user_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
        query_text="COMMAND: /reset",
    )
    session_id = str(message.chat.id)
    memory = get_chat_memory(session_id=session_id)
    await memory.chat_memory.clear()
    await message.answer(RESET_CONFIRMATION_TEXT)

async def _pin_message_and_delete_notification(bot: Bot, chat_id: int, message_id: int):
    """
    Pins a message and immediately tries to delete the service message about the pin.
    This is a workaround for cases where `disable_notification=True` doesn't prevent
    the "Bot pinned a message" service message from appearing in the chat.
    """
    try:
        await bot.pin_chat_message(
            chat_id=chat_id,
            message_id=message_id,
            disable_notification=True
        )
        # The service message about pinning is usually the next message.
        # We attempt to delete it to keep the chat clean.
        await bot.delete_message(chat_id=chat_id, message_id=message_id + 1)
    except TelegramBadRequest as e:
        # Ignore errors if the service message wasn't created, already deleted,
        # or if we lack permissions. This makes the function robust.
        if "message to delete not found" not in str(e) and "message can't be deleted" not in str(e):
            logging.warning(f"Could not delete pin notification for message {message_id} in chat {chat_id}: {e}")

async def _update_calculator_message(
    state: FSMContext,
    bot: Bot,
    chat_id: int,
    text: str,
    reply_markup: InlineKeyboardMarkup,
):
    """
    A robust helper to update the main calculator message.
    It reads the message ID and its type (photo or text) from the state
    and uses the appropriate edit method.
    """
    user_data = await state.get_data()
    message_id = user_data.get("calculator_message_id")
    has_photo = user_data.get("has_photo", False)

    if not message_id:
        logging.error(f"Cannot update calculator: message_id not found in state for chat {chat_id}.")
        return

    try:
        if has_photo:
            await bot.edit_message_caption(
                chat_id=chat_id, message_id=message_id, caption=text, reply_markup=reply_markup
            )
        else:
            await bot.edit_message_text(
                chat_id=chat_id, message_id=message_id, text=text, reply_markup=reply_markup
            )
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            logging.error(f"Failed to update calculator message {message_id} in chat {chat_id}: {e}", exc_info=True)


async def _update_calculator_widget(
    state: FSMContext,
    bot: Bot,
    chat_id: int,
    text: str,
    reply_markup: InlineKeyboardMarkup,
    photo_path: str | None = None,
):
    """
    A wrapper function to update the main calculator message, handling photo changes
    and updating FSM state for message_id and has_photo.
    """
    user_data = await state.get_data()
    message_id = user_data.get("calculator_message_id")
    current_has_photo = user_data.get("has_photo", False)
    current_photo_path = user_data.get("current_photo_path")

    if not message_id:
        logging.error(f"Cannot update calculator widget: message_id not found in state for chat {chat_id}.")
        return

    # Determine if the desired photo status is different from the current one
    desired_has_photo = bool(photo_path and Path(photo_path).is_file())

    if desired_has_photo != current_has_photo or (desired_has_photo and photo_path != current_photo_path):
        # If there's a change in photo status (add/remove photo) or a new photo path is specified, use _edit_message
        new_message_id, new_has_photo = await _edit_message(
            bot=bot,
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            reply_markup=reply_markup,
            photo_path=photo_path,
            has_photo=current_has_photo,
        )
        # Update FSM state with the new message details
        await state.update_data(
            calculator_message_id=new_message_id, 
            has_photo=new_has_photo, 
            current_photo_path=photo_path if new_has_photo else None
        )
    else:
        # If no change in photo status, just edit the existing message (caption or text)
        await _update_calculator_message(state=state, bot=bot, chat_id=chat_id, text=text, reply_markup=reply_markup)


async def _edit_message(
    bot: Bot,
    chat_id: int,
    message_id: int,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    photo_path: str | None = None,
    has_photo: bool = False,
) -> tuple[int, bool]:
    """
    Edits a message, robustly handling transitions between text-only and photo-with-caption states.
    Returns a tuple (new_message_id, new_has_photo) to handle cases where the message is replaced.

    Args:
        bot: The Bot instance.
        chat_id: The ID of the chat where the message is.
        message_id: The ID of the message to edit.
        text: The new text for the message or caption.
        reply_markup: The new inline keyboard.
        photo_path: The path to a new photo, if any.
        has_photo: A boolean indicating if the original message has a photo.

    Returns:
        A tuple containing the potentially new message ID and the new photo status.
    """
    try:
        new_photo_exists = photo_path and Path(photo_path).is_file()

        # Case 1: Transition from Text to Photo
        if new_photo_exists and not has_photo:
            await bot.delete_message(chat_id=chat_id, message_id=message_id)
            new_message = await bot.send_photo(chat_id=chat_id, photo=FSInputFile(photo_path), caption=text, reply_markup=reply_markup)
            return new_message.message_id, True

        # Case 2: Transition from Photo to Text
        elif not new_photo_exists and has_photo:
            await bot.delete_message(chat_id=chat_id, message_id=message_id)
            new_message = await bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)
            return new_message.message_id, False

        # Case 3: Both are Photos (or new photo provided for existing photo message)
        elif new_photo_exists and has_photo:
            media = InputMediaPhoto(media=FSInputFile(photo_path), caption=text)
            await bot.edit_message_media(chat_id=chat_id, message_id=message_id, media=media, reply_markup=reply_markup)
            return message_id, True

        # Case 4: Both are Text (or no photo provided for existing text message)
        else:
            await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=reply_markup)
            return message_id, False

    except TelegramBadRequest as e:
        # Ignore "message is not modified" error which occurs on rapid clicks.
        if "message is not modified" in str(e):
            return message_id, has_photo
        else:
            logging.error(f"Error editing message: {e}", exc_info=True)
            raise
    return message_id, has_photo


async def _edit_caption(
    bot: Bot,
    chat_id: int,
    message_id: int,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None
):
    """
    A helper function to only edit the caption of a message that is known to have a photo.
    """
    try:
        await bot.edit_message_caption(
            chat_id=chat_id,
            message_id=message_id,
            caption=text,
            reply_markup=reply_markup
        )
    except TelegramBadRequest as e:
        # Ignore "message is not modified" error.
        if "message is not modified" in str(e):
            pass
        else:
            logging.error(f"Error editing caption: {e}", exc_info=True)
            raise

async def process_query(
    chat_id: int, user_question: str, bot: Bot, message_to_answer: Message, user: User
):
    """A reusable function to process a user's query through the RAG chain.

    Args:
        chat_id: The user's chat ID for session management.
        user_question: The question to be processed.
        bot: The Bot instance to send 'typing' action.
        message_to_answer: The Message object to reply to or edit.
        user: The User object of the person who initiated the query.
    """
    # 1. Provide user feedback that the request is being processed
    await bot.send_chat_action(chat_id=chat_id, action="typing")

    # 2. Create an instance of the callback handler to log fallbacks
    fallback_logger = FallbackLoggingCallbackHandler()

    # 3. Get the RAG chain and invoke it with the user's question
    rag_chain = get_rag_chain()
    try:
        result = await rag_chain.ainvoke(
            {"session_id": str(chat_id), "question": user_question},
            # Pass the callback handler to the chain invocation for logging
            config={"callbacks": [fallback_logger]},
        )
        ai_response = result["answer"]
        retrieved_context = result["context"]

        # 4. Prepare and send the response with robust fallback logic.
        text_to_send = ai_response
        if settings.SANITIZE_RESPONSE:
            text_to_send = sanitize_for_telegram_markdown(ai_response)

        try:
            # First attempt: send with Markdown.
            await message_to_answer.answer(text_to_send, parse_mode="Markdown")
        except TelegramBadRequest as e:
            # This error indicates a problem with Markdown parsing.
            if "can't parse entities" in str(e):
                logging.warning(
                    f"Markdown parsing failed for user {chat_id}. "
                    f"Applying legacy escape and retrying. Original error: {e}"
                )
                # Second attempt: escape problematic characters and retry.
                # We escape the already sanitized text that caused the error.
                escaped_text = escape_markdown_legacy(text_to_send)
                try:
                    await message_to_answer.answer(escaped_text, parse_mode="Markdown")
                except TelegramBadRequest as e2:
                    # Third and final attempt: send as plain text if escaping also fails.
                    logging.error(
                        f"Fallback with escaped Markdown also failed for user {chat_id}. "
                        f"Sending as plain text. Error: {e2}",
                        exc_info=True,
                    )
                    # Send the original, raw AI response without any formatting.
                    await message_to_answer.answer(ai_response, parse_mode=None)
            else:
                # Re-raise other Telegram-related errors.
                raise

        # 5. Log the query and response to the statistics database
        await log_query(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            query_text=user_question,
            retrieved_context=retrieved_context,
            llm_response=ai_response,
        )

        # 6. Manually save the context to the chat history
        # The RAG chain loads history, but saving is handled here.
        memory = get_chat_memory(session_id=str(chat_id))
        await memory.chat_memory.add_messages(
            [HumanMessage(content=user_question), AIMessage(content=ai_response)]
        )
    except Exception as e:
        # Log the full error for debugging purposes
        logging.error(f"Error processing message for user {chat_id}: {e}", exc_info=True)
        # Inform the user that an error occurred
        error_text = (
            "⚠️ К сожалению, произошла ошибка при обработке вашего запроса.\n"
            "Пожалуйста, попробуйте еще раз позже.\n"
        )
        await message_to_answer.answer(error_text)


@router.callback_query(ActionCallback.filter())
async def handle_actions(query: CallbackQuery, callback_data: ActionCallback, bot: Bot, state: FSMContext):
    """
    Handles callbacks from general action buttons, like those in the /help menu.
    This handler is separate from the catalog navigation logic.
    """
    await query.answer()  # Acknowledge the callback
    if not query.message:
        return

    action = callback_data.name
    user = query.from_user

    if action == "restart":
        await log_query(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            query_text="CLICK: Restart Bot",
        )
        # Re-trigger the /start handler to send a fresh welcome message.
        # We need to pass the state and bot to the start handler.
        await handle_start(query.message, state, bot)

    elif action == "reset":
        await log_query(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            query_text="CLICK: Reset Chat",
        )
        # Replicate the /reset logic for the callback button.
        await handle_reset(query.message)


@router.callback_query(CatalogCallback.filter())
async def navigate_catalog(
    query: CallbackQuery, callback_data: CatalogCallback, state: FSMContext, bot: Bot
):
    """Handles navigation through the sales funnel using callbacks."""
    await query.answer()
    if not query.message:
        return

    # Log the button click to statistics
    log_text = f"CLICK: {callback_data.action}"
    if callback_data.item_id:
        log_text += f" (item: {callback_data.item_id})"

    await log_query(
        user_id=query.from_user.id,
        username=query.from_user.username,
        first_name=query.from_user.first_name,
        last_name=query.from_user.last_name,
        query_text=log_text,
    )

    # Get the calculator message ID from the state.
    user_data = await state.get_data()
    message_id = user_data.get("calculator_message_id")

    if not message_id:
        # If for some reason the ID is lost, we can't proceed with editing.
        # We can try to use the current message, but it's better to log and potentially restart.
        logging.error(f"Calculator message ID not found in state for user {query.from_user.id}. Aborting navigation.")
        message_id = query.message.message_id

    level = callback_data.level

    # Level 0: Back to start
    if level == 0:
        # When returning to the main menu, we want to show the welcome message and photo.
        await _update_calculator_widget(
            state=state,
            bot=bot,
            chat_id=query.message.chat.id,
            text=START_MESSAGE_TEXT,
            reply_markup=get_start_keyboard(),
            photo_path=settings.WELCOME_PHOTO_PATH,
        )
        await state.set_state(None)

    # Level 1: Product categories
    elif level == 1:
        # When returning to the catalog, show the catalog message and photo.
        await _update_calculator_widget(
            state=state,
            bot=bot,
            chat_id=query.message.chat.id,
            text=CATALOG_MESSAGE_TEXT,
            reply_markup=get_catalog_keyboard(),
            photo_path=settings.CATALOG_PHOTO_PATH,
        )
        await state.set_state(None)

    # Level 2: Product selected (Banners)
    elif level == 2:
        # Show banners message and photo
        await _update_calculator_widget(
            state=state,
            bot=bot,
            chat_id=query.message.chat.id,
            text=BANNERS_MESSAGE_TEXT,
            reply_markup=get_banner_materials_keyboard(),
            photo_path=settings.BANNERS_PHOTO_PATH,
        )
        await state.set_state(None)

    # Level 3: Material selected
    elif level == 3:
        photo_path_for_step = settings.BANNERS_PHOTO_PATH

        # This handles both selecting a new material and going "back" to the size input step
        if callback_data.action == "back_to_material_input":
            # If user goes back, we need to revert the state and the message
            await state.set_state(OrderState.entering_size)
            material_name = user_data.get("material_name", "N/A")
            text = MATERIAL_SELECTED_TEXT.format(material_name=material_name)
            reply_markup = get_back_button_keyboard(return_level=2, return_action="back_to_materials")
            await _update_calculator_widget(
                state=state,
                bot=bot, 
                chat_id=query.message.chat.id,
                text=text,
                reply_markup=reply_markup,
                photo_path=photo_path_for_step,
            )

        elif callback_data.action == "select_material" and callback_data.item_id:
            await state.set_state(OrderState.entering_size)

            material_name = MATERIAL_NAME_MAP.get(callback_data.item_id, "Неизвестный материал")
            text = MATERIAL_SELECTED_TEXT.format(material_name=material_name)
            reply_markup = get_back_button_keyboard(return_level=2, return_action="back_to_materials")

            await state.update_data(material_id=callback_data.item_id, material_name=material_name)

            await _update_calculator_widget(
                state=state,
                bot=bot, 
                chat_id=query.message.chat.id,
                text=text,
                reply_markup=reply_markup,
                photo_path=photo_path_for_step,
            )

    # Level 4: Print quality selected
    elif level == 4:
        photo_path_for_step = settings.BANNERS_PHOTO_PATH

        if callback_data.action == "back_to_quality_selection":
            await state.set_state(OrderState.choosing_print_quality)
            text = PROMPT_FOR_QUALITY_TEXT.format(
                material_name=user_data.get("material_name", "N/A"),
                width=user_data.get("width", 0),
                height=user_data.get("height", 0),
            )
            await _update_calculator_widget(
                state=state, bot=bot, chat_id=query.message.chat.id, text=text, reply_markup=get_print_quality_keyboard(),
                photo_path=photo_path_for_step,
            )

        elif callback_data.action == "select_quality" and callback_data.item_id:
            await state.update_data(quality=callback_data.item_id)
            await state.set_state(OrderState.choosing_processing_type)

            text = PROMPT_FOR_PROCESSING_TEXT.format(
                material_name=user_data.get("material_name", "N/A"),
                width=user_data.get("width", 0),
                height=user_data.get("height", 0),
                quality=callback_data.item_id
            )

            await _update_calculator_widget(
                state=state,
                bot=bot, 
                chat_id=query.message.chat.id,
                text=text,
                reply_markup=get_processing_type_keyboard(),
                photo_path=photo_path_for_step,
            )
    
    # Level 5: Processing type selected
    elif level == 5:
        photo_path_for_step = settings.BANNERS_PHOTO_PATH

        if callback_data.action == "back_to_processing_selection":
            await state.set_state(OrderState.choosing_processing_type)
            text = PROMPT_FOR_PROCESSING_TEXT.format(
                material_name=user_data.get("material_name", "N/A"),
                width=user_data.get("width", 0),
                height=user_data.get("height", 0),
                quality=user_data.get("quality", "N/A"),
            )
            await _update_calculator_widget(
                state=state, bot=bot, chat_id=query.message.chat.id, text=text, reply_markup=get_processing_type_keyboard(),
                photo_path=photo_path_for_step,
            )

        elif callback_data.action == "select_processing" and callback_data.item_id:
            processing_map = {
                "grommets": "Установка люверсов",
                "pockets": "Проварка карманов",
                "welded_edges": "Проварка краёв без люверсов",
                "cut_off": "Под обрез",
            }
            processing_text = processing_map.get(callback_data.item_id, "Не выбрана")
            await state.update_data(processing=processing_text)

            await state.set_state(OrderState.choosing_quantity)

            text = PROMPT_FOR_QUANTITY_TEXT.format(
                material_name=user_data.get("material_name", "N/A"),
                width=user_data.get("width", 0),
                height=user_data.get("height", 0),
                quality=user_data.get("quality", "N/A"),
                processing=processing_text,
            )

            await _update_calculator_widget(
                state=state, bot=bot, chat_id=query.message.chat.id, text=text, reply_markup=get_quantity_keyboard(),
                photo_path=photo_path_for_step,
            )

    # Level 6: Quantity selected
    elif level == 6:
        photo_path_for_step = settings.BANNERS_PHOTO_PATH

        if callback_data.action == "back_to_quantity_selection":
            await state.set_state(OrderState.choosing_quantity)
            text = PROMPT_FOR_QUANTITY_TEXT.format(
                material_name=user_data.get("material_name", "N/A"),
                width=user_data.get("width", 0),
                height=user_data.get("height", 0),
                quality=user_data.get("quality", "N/A"),
                processing=user_data.get("processing", "N/A"),
            )
            await _update_calculator_widget(
                state=state, bot=bot, chat_id=query.message.chat.id, text=text, reply_markup=get_quantity_keyboard(),
                photo_path=photo_path_for_step,
            )

        elif callback_data.action == "select_quantity" and callback_data.item_id:
            await state.update_data(quantity=int(callback_data.item_id))
            await state.set_state(OrderState.choosing_urgency)

            text = PROMPT_FOR_URGENCY_TEXT.format(
                material_name=user_data.get("material_name", "N/A"),
                width=user_data.get("width", 0),
                height=user_data.get("height", 0),
                quality=user_data.get("quality", "N/A"),
                processing=user_data.get("processing", "N/A"),
                quantity=callback_data.item_id,
            )
            await _update_calculator_widget(
                state=state, bot=bot, chat_id=query.message.chat.id, text=text, reply_markup=get_urgency_keyboard(),
                photo_path=photo_path_for_step,
            )

        elif callback_data.action == "enter_quantity":
            await state.set_state(OrderState.entering_quantity)
            text = PROMPT_FOR_MANUAL_QUANTITY_TEXT.format(
                material_name=user_data.get("material_name", "N/A"),
                width=user_data.get("width", 0),
                height=user_data.get("height", 0),
                quality=user_data.get("quality", "N/A"),
                processing=user_data.get("processing", "N/A"),
            )
            await _update_calculator_widget(
                state=state, bot=bot, chat_id=query.message.chat.id, text=text, reply_markup=get_back_button_keyboard(5, "back_to_processing_selection"),
                photo_path=photo_path_for_step,
            )

    # Level 7: Urgency selected
    elif level == 7:
        photo_path_for_step = settings.BANNERS_PHOTO_PATH

        if callback_data.action == "back_to_urgency_selection":
            await state.set_state(OrderState.choosing_urgency)
            text = PROMPT_FOR_URGENCY_TEXT.format(
                material_name=user_data.get("material_name", "N/A"),
                width=user_data.get("width", 0),
                height=user_data.get("height", 0),
                quality=user_data.get("quality", "N/A"),
                processing=user_data.get("processing", "N/A"),
                quantity=user_data.get("quantity", 1),
            )
            await _update_calculator_widget(
                state=state, bot=bot, chat_id=query.message.chat.id, text=text, reply_markup=get_urgency_keyboard(),
                photo_path=photo_path_for_step,
            )

        elif callback_data.action == "select_urgency" and callback_data.item_id:
            is_urgent = callback_data.item_id == "urgent"
            urgency_text = "Срочный (1 день)" if is_urgent else "Обычный (2-3 дня)"
            await state.update_data(is_urgent=is_urgent, urgency_text=urgency_text)
            await state.set_state(OrderState.choosing_delivery)

            current_data = await state.get_data()
            text = PROMPT_FOR_DELIVERY_TEXT.format(
                material_name=current_data.get("material_name", "N/A"),
                width=current_data.get("width", 0),
                height=current_data.get("height", 0),
                quality=current_data.get("quality", "N/A"),
                processing=current_data.get("processing", "N/A"),
                quantity=current_data.get("quantity", 1),
                urgency=urgency_text,
            )
            await _update_calculator_widget(
                state=state, bot=bot, chat_id=query.message.chat.id, text=text, reply_markup=get_delivery_keyboard(),
                photo_path=photo_path_for_step,
            )

    # Level 8: Delivery selected (Final calculation step)
    elif level == 8:
        photo_path_for_step = settings.CALCULATION_PHOTO_PATH

        if callback_data.action == "back_to_delivery_selection":
            await state.set_state(OrderState.choosing_delivery)
            current_data = await state.get_data()
            text = PROMPT_FOR_DELIVERY_TEXT.format(
                material_name=current_data.get("material_name", "N/A"),
                width=current_data.get("width", 0),
                height=current_data.get("height", 0),
                quality=current_data.get("quality", "N/A"),
                processing=current_data.get("processing", "N/A"),
                quantity=current_data.get("quantity", 1),
                urgency=current_data.get("urgency_text", "N/A"),
            )
            # When going back, we should revert to the previous image
            await _update_calculator_widget(
                state=state, bot=bot, chat_id=query.message.chat.id, text=text, reply_markup=get_delivery_keyboard(), photo_path=settings.BANNERS_PHOTO_PATH
            )

        if callback_data.action == "select_delivery" and callback_data.item_id:
            needs_delivery = callback_data.item_id == "yes"
            delivery_method = "Доставка (350р.)" if needs_delivery else "Самовывоз"
            await state.update_data(delivery_method=delivery_method)

            # Recalculate final price including delivery
            # We need to get the quantity from state now
            current_data = await state.get_data()
            final_price = calculate_price(
                product="banners",
                material=current_data.get("material_id"),
                width=current_data.get("width", 0),
                height=current_data.get("height", 0),
                dpi=current_data.get("quality"),
                is_urgent=current_data.get("is_urgent", False),
                quantity=current_data.get("quantity", 1),
                needs_delivery=needs_delivery,
            )

            if final_price is None:
                error_text = "Не удалось рассчитать стоимость. Пожалуйста, попробуйте снова или свяжитесь с менеджером."
                await _update_calculator_widget(
                    state=state, bot=bot, chat_id=query.message.chat.id, text=error_text, reply_markup=get_back_button_keyboard(1, "back_to_catalog"),
                    photo_path=settings.BANNERS_PHOTO_PATH,
                )
                await state.clear()
                return

            await state.update_data(final_price=final_price)
            await state.set_state(OrderState.final_confirmation)

            text = FINAL_CALCULATION_TEXT.format(
                material_name=current_data.get("material_name", "N/A"),
                width=current_data.get("width", 0),
                height=current_data.get("height", 0),
                quality=current_data.get("quality", "N/A"),
                processing=current_data.get("processing", "N/A"),
                quantity=current_data.get("quantity", 1),
                urgency=current_data.get("urgency_text", "N/A"),
                delivery_method=delivery_method,
                price=final_price,
            )

            await _update_calculator_widget(
                state=state,
                bot=bot,
                chat_id=query.message.chat.id,
                text=text,
                reply_markup=get_order_keyboard(),
                photo_path=photo_path_for_step,
            )
    
    # Level 9: Order Confirmation
    elif level == 9:
        photo_path_for_step = settings.ORDER_PHOTO_PATH
        if callback_data.action == "confirm_order":
            current_data = await state.get_data()
            # Escape the username to prevent Markdown parsing errors while keeping it clickable.
            escaped_username = escape_markdown_legacy(query.from_user.username or "N/A")
            
            # Send notification to manager
            manager_text = MANAGER_ORDER_NOTIFICATION_TEXT.format(
                username=escaped_username,
                material_name=current_data.get("material_name", "N/A"),
                width=current_data.get("width", 0),
                height=current_data.get("height", 0),
                quality=current_data.get("quality", "N/A"),
                processing=current_data.get("processing", "N/A"),
                quantity=current_data.get("quantity", 1),
                urgency=current_data.get("urgency_text", "N/A"),
                delivery_method=current_data.get("delivery_method", "N/A"),
                price=current_data.get("final_price", 0.0),
            )
            await bot.send_message(chat_id=settings.MANAGER_CHAT_ID, text=manager_text, parse_mode="Markdown")

            # Update user's message
            user_text = ORDER_CONFIRMED_TEXT.format(
                material_name=current_data.get("material_name", "N/A"),
                width=current_data.get("width", 0),
                height=current_data.get("height", 0),
                quality=current_data.get("quality", "N/A"),
                processing=current_data.get("processing", "N/A"),
                quantity=current_data.get("quantity", 1),
                urgency=current_data.get("urgency_text", "N/A"),
                delivery_method=current_data.get("delivery_method", "N/A"),
                price=current_data.get("final_price", 0.0),
            )
            await _update_calculator_widget(
                state=state,
                bot=bot,
                chat_id=query.message.chat.id,
                text=user_text,
                reply_markup=get_manager_contact_keyboard(),
                photo_path=photo_path_for_step,
            )
            await state.clear()


@router.message(OrderState.entering_size, F.text.regexp(r"^\s*(\d+(?:[.,]\d+)?)\s*(?:[xх]|\*|на)\s*(\d+(?:[.,]\d+)?)\s*$"))
async def handle_size_input(message: Message, state: FSMContext, bot: Bot):
    """Handles size input, saves it to state, and transitions to the next step (print quality)."""
    # Delete the user's message with the size to keep the chat clean.
    await message.delete()

    size_match = re.match(r"^\s*(\d+(?:[.,]\d+)?)\s*(?:[xх]|\*|на)\s*(\d+(?:[.,]\d+)?)\s*$", message.text.lower())

    if not size_match:
        await message.reply(
            "Неверный формат. Пожалуйста, введите размер в формате `Ширина x Высота`, например: `3 x 2`"
        )
        return

    # Extract and convert dimensions to float
    width = float(size_match.group(1).replace(",", "."))
    height = float(size_match.group(2).replace(",", "."))

    # Retrieve material from state
    user_data = await state.get_data()
    message_id = user_data.get("calculator_message_id")
    material_id = user_data.get("material_id")

    if not material_id or not message_id:
        await message.answer("Произошла ошибка, не удалось определить параметры заказа. Пожалуйста, начните заново с /catalog.")
        await state.clear()
        return

    # Save dimensions to state
    await state.update_data(width=width, height=height)

    # Transition to the next state
    await state.set_state(OrderState.choosing_print_quality)

    material_name = MATERIAL_NAME_MAP.get(material_id, "N/A")
    await state.update_data(material_name=material_name) # Save for later steps
    text = PROMPT_FOR_QUALITY_TEXT.format(material_name=material_name, width=width, height=height)

    # Edit the calculator message to show the next step
    await _update_calculator_widget(
        state=state,
        bot=bot,
        chat_id=message.chat.id,
        text=text,
        reply_markup=get_print_quality_keyboard(),
        photo_path=settings.BANNERS_PHOTO_PATH,
    )


@router.message(OrderState.entering_quantity, F.text.regexp(r"^\d+$"))
async def handle_quantity_input(message: Message, state: FSMContext, bot: Bot):
    """Handles manual quantity input, saves it, and transitions to the delivery step."""
    await message.delete()

    quantity = int(message.text)
    if quantity <= 0:
        # This case is unlikely if the regex is correct, but good for robustness
        return

    await state.update_data(quantity=quantity)
    await state.set_state(OrderState.choosing_urgency)

    user_data = await state.get_data()

    text = PROMPT_FOR_URGENCY_TEXT.format(
        material_name=user_data.get("material_name", "N/A"),
        width=user_data.get("width", 0),
        height=user_data.get("height", 0),
        quality=user_data.get("quality", "N/A"),
        processing=user_data.get("processing", "N/A"),
        quantity=quantity,
    )

    await _update_calculator_widget(
        state=state,
        bot=bot,
        chat_id=message.chat.id,
        text=text,
        reply_markup=get_urgency_keyboard(),
        photo_path=settings.BANNERS_PHOTO_PATH,
    )


@router.message(StateFilter(OrderState), F.text)
async def handle_question_in_funnel(message: Message, bot: Bot, state: FSMContext):
    """
    Handles general text questions from the user while they are inside the sales funnel.
    This allows the user to ask the AI for clarification without breaking the funnel flow.
    Any text that doesn't match a specific state's filter (like the size format) will be caught here.
    """
    if not message.text:
        return

    # The user is asking a question, so we process it through the RAG chain.
    # The state of the funnel is preserved.
    await process_query(
        chat_id=message.chat.id,
        user_question=message.text,
        bot=bot,
        message_to_answer=message,
        user=message.from_user,
    )

@router.message(StateFilter(None), F.text)
async def handle_message(message: Message, bot: Bot):
    """Handles incoming text messages by passing them to the query processor."""
    if not message.text:
        return

    await process_query(
        chat_id=message.chat.id,
        user_question=message.text,
        bot=bot,
        message_to_answer=message,
        user=message.from_user,
    )