# app/handlers/user_handlers.py

import logging
from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile, Message, User
from langchain_core.messages import AIMessage, HumanMessage

from app.config import settings
from app.core.chain import FallbackLoggingCallbackHandler, get_rag_chain
from app.core.memory import get_chat_memory
from app.core.stats import log_query
from app.utils.text_formatters import escape_markdown_legacy, sanitize_for_telegram_markdown
from app.keyboards import ActionCallback, get_help_keyboard, get_start_keyboard

# Create a new Router instance for user-facing handlers.
router = Router()

# Define the welcome message as a constant for reusability.
START_MESSAGE_TEXT = (
    "Приветствую, например!\n\n"
    "С вами Паук, вождь КТР. Готов котировать ваши вопросы в режиме дичайшего угара, тащемта!\n\n"
    "Задавай вопрос, человек — устроим моднейший перформанс!"
)

# Define the static text for the "/help" command.
HELP_MESSAGE_TEXT = (
    "**🫂 Возможные проблемы и решения:**\n\n"
    "1. Ответ ИИ может занять 5-10 секунд. Пожалуйста, подождите, например.\n"
    "2. Если бот не отвечает, попробуйте перезапустить командой: /start\n"
    "3. Если AI сбился с темы, используйте команду /reset, чтобы очистить историю чата.\n\n"
    "**🗣 Прямая связь:**\n"
    "Если вы хотите такого бота, "
    "напишите мне в Telegram: @mynamemyway"
)

# Define the confirmation text for the /reset command.
RESET_CONFIRMATION_TEXT = "🧹 История диалога успешно очищена, например!"


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
    await state.clear()  # Clear previous funnel state if any
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


@router.message(F.text)
async def handle_message(message: Message, bot: Bot):
    """
    Handles incoming text messages by passing them to the query processor.

    In group chats, if REPLY_ONLY_TO_MENTIONS is True, the bot only responds
    when explicitly mentioned via @bot_username. In private chats, the bot
    always responds.
    """
    if not message.text:
        return

    # Check if we should process this message based on chat type and mention settings
    if not await _should_process_message(message, bot):
        return

    await process_query(
        chat_id=message.chat.id,
        user_question=message.text,
        bot=bot,
        message_to_answer=message,
        user=message.from_user,
    )


async def _should_process_message(message: Message, bot: Bot) -> bool:
    """
    Determines if the bot should process a message based on chat type and mention settings.

    Args:
        message: The incoming message to check.
        bot: The Bot instance for getting username.

    Returns:
        True if the message should be processed, False otherwise.
    """
    # In private chats, always process messages
    if message.chat.type == "private":
        return True

    # In group chats, check the REPLY_ONLY_TO_MENTIONS setting
    if settings.REPLY_ONLY_TO_MENTIONS:
        # Check if the bot is mentioned in the message
        return await _is_bot_mentioned(message, bot)

    # If REPLY_ONLY_TO_MENTIONS is False, process all messages in groups
    return True


async def _is_bot_mentioned(message: Message, bot: Bot) -> bool:
    """
    Checks if the bot is mentioned in the message text.

    Args:
        message: The incoming message to check.
        bot: The Bot instance for getting username.

    Returns:
        True if the bot is mentioned, False otherwise.
    """
    if not message.text:
        return False

    # Get bot username via API call
    bot_me = await bot.get_me()
    bot_username = bot_me.username
    if not bot_username:
        # Fallback: if username is not available, allow the message
        return True

    # Check for mention in format @bot_username (case-insensitive)
    mention = f"@{bot_username}"
    return mention.lower() in message.text.lower()
