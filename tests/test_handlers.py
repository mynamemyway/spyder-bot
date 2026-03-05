"""
Модульные тесты для обработчиков aiogram в app/handlers/user_handlers.py.

Используется pytest и pytest-asyncio для асинхронного тестирования.
Внешние зависимости, такие как RAG-цепочка, база данных и вызовы API Telegram,
полностью мокируются с помощью unittest.mock.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from aiogram.fsm.context import FSMContext
from aiogram.types import Message, InlineKeyboardMarkup, CallbackQuery, Chat

from app.handlers import user_handlers
from app.keyboards import (
    get_start_keyboard, get_catalog_keyboard, get_banner_materials_keyboard,
    get_back_button_keyboard, get_processing_type_keyboard, CatalogCallback
    , get_print_quality_keyboard, get_urgency_keyboard, # Added get_urgency_keyboard

    ActionCallback # Added ActionCallback
) # Added get_print_quality_keyboard
from app.handlers.user_handlers import (
    START_MESSAGE_TEXT,
    CATALOG_MESSAGE_TEXT,
    RESET_CONFIRMATION_TEXT,
    BANNERS_MESSAGE_TEXT,
    MATERIAL_SELECTED_TEXT,
    PROMPT_FOR_PROCESSING_TEXT,
    OrderState,
    PROMPT_FOR_QUALITY_TEXT, # Added PROMPT_FOR_QUALITY_TEXT
    PROMPT_FOR_URGENCY_TEXT, # Added PROMPT_FOR_URGENCY_TEXT
    RESET_CONFIRMATION_TEXT, # Added RESET_CONFIRMATION_TEXT
    MATERIAL_NAME_MAP,
)

# Используем pytest-asyncio для всех тестов в этом файле
pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize(
    "command_handler, command_text, message_text, keyboard_func, photo_path_attr",
    [
        (user_handlers.handle_start, "COMMAND: /start", START_MESSAGE_TEXT, get_start_keyboard, "WELCOME_PHOTO_PATH"),
        (user_handlers.handle_catalog, "COMMAND: /catalog", CATALOG_MESSAGE_TEXT, get_catalog_keyboard, "CATALOG_PHOTO_PATH"),
    ],
)
@pytest.mark.parametrize(
    "has_photo, is_file",
    [(True, True), (True, False), (False, False)],
    ids=["with_photo", "photo_path_set_but_not_found", "without_photo"]
)
@patch("app.handlers.user_handlers.log_query", new_callable=AsyncMock)
@patch("app.handlers.user_handlers._pin_message_and_delete_notification", new_callable=AsyncMock)
@patch("pathlib.Path.is_file")
@patch("app.handlers.user_handlers.settings")
async def test_start_and_catalog_commands(
    mock_settings, mock_is_file, mock_pin, mock_log,
    mock_bot, mock_message, mock_fsm_context,
    command_handler, command_text, message_text, keyboard_func, photo_path_attr,
    has_photo, is_file
):
    """Тестирует команды /start и /catalog в различных сценариях (с фото и без)."""
    # Настройка моков
    setattr(mock_settings, photo_path_attr, "fake/path.jpg" if has_photo else None)
    mock_is_file.return_value = is_file
    mock_keyboard = MagicMock(spec=InlineKeyboardMarkup)
    
    # Мокируем возвращаемое значение для нового виджета, чтобы получить его ID
    new_widget_message = MagicMock(spec=Message)
    new_widget_message.message_id = 999
    # Явно создаем мок для вложенного объекта chat
    new_widget_message.chat = MagicMock(spec=Chat)
    new_widget_message.chat.id = mock_message.chat.id
    new_widget_message.photo = [1] if has_photo and is_file else [] # Эмулируем наличие фото
    mock_message.answer.return_value = new_widget_message
    mock_message.answer_photo.return_value = new_widget_message

    # Вызов обработчика
    await command_handler(mock_message, mock_fsm_context, mock_bot)

    # Проверки
    # 1. Проверка логирования
    mock_log.assert_called_once_with(
        user_id=mock_message.from_user.id,
        username=mock_message.from_user.username,
        first_name=mock_message.from_user.first_name,
        last_name=mock_message.from_user.last_name,
        query_text=command_text,
    )

    # 2. Проверка отправки сообщения (с фото или без)
    if has_photo and is_file:
        mock_message.answer_photo.assert_called_once()
        _, kwargs = mock_message.answer_photo.call_args
        assert kwargs["caption"] == message_text
        assert isinstance(kwargs["reply_markup"], InlineKeyboardMarkup)
        mock_message.answer.assert_not_called()
    else:
        mock_message.answer.assert_called_once_with(message_text, reply_markup=keyboard_func())
        mock_message.answer_photo.assert_not_called()

    # 3. Проверка закрепления сообщения
    mock_pin.assert_called_once_with(mock_bot, new_widget_message.chat.id, new_widget_message.message_id)

    # 4. Проверка управления состоянием FSM
    state_data = await mock_fsm_context.get_data()
    assert state_data["calculator_message_id"] == new_widget_message.message_id
    assert state_data["has_photo"] == (has_photo and is_file)


@patch("app.handlers.user_handlers.log_query", new_callable=AsyncMock)
async def test_start_deletes_old_widget(mock_log, mock_bot, mock_message, mock_fsm_context: FSMContext):
    """Проверяет, что /start удаляет старый виджет, если его ID есть в состоянии."""
    # Настройка моков
    old_widget_id = 100
    await mock_fsm_context.update_data(calculator_message_id=old_widget_id)

    # Мокируем внутренние вызовы, чтобы изолировать тест
    with patch("app.handlers.user_handlers._pin_message_and_delete_notification", new_callable=AsyncMock):
        # Вызов обработчика
        await user_handlers.handle_start(mock_message, mock_fsm_context, mock_bot)

    # Проверка
    mock_bot.delete_message.assert_called_once_with(
        chat_id=mock_message.chat.id, message_id=old_widget_id
    )


@patch("app.handlers.user_handlers.log_query", new_callable=AsyncMock)
@patch("app.handlers.user_handlers.get_chat_memory")
async def test_reset_command(mock_get_chat_memory, mock_log, mock_message, mock_fsm_context: FSMContext):
    """Тестирует команду /reset."""
    # Настройка моков
    mock_memory_instance = MagicMock()
    mock_memory_instance.chat_memory.clear = AsyncMock()
    mock_get_chat_memory.return_value = mock_memory_instance

    # Устанавливаем начальное состояние, чтобы убедиться, что оно НЕ очищается
    await mock_fsm_context.set_state("some_state")
    await mock_fsm_context.update_data(some_data="some_value")

    # Вызов обработчика
    await user_handlers.handle_reset(mock_message)

    # Проверки
    # 1. Проверка логирования
    mock_log.assert_called_once_with(
        user_id=mock_message.from_user.id,
        username=mock_message.from_user.username,
        first_name=mock_message.from_user.first_name,
        last_name=mock_message.from_user.last_name,
        query_text="COMMAND: /reset",
    )

    # 2. Проверка очистки истории чата
    mock_get_chat_memory.assert_called_once_with(session_id=str(mock_message.chat.id))
    mock_memory_instance.chat_memory.clear.assert_called_once()

    # 3. Проверка ответа пользователю
    mock_message.answer.assert_called_once_with(RESET_CONFIRMATION_TEXT)

    # 4. Проверка, что состояние FSM НЕ было очищено
    current_state = await mock_fsm_context.get_state()
    current_data = await mock_fsm_context.get_data()
    assert current_state == "some_state"
    assert current_data == {"some_data": "some_value"}


@pytest.mark.parametrize(
    "level, action, item_id, initial_state_data, expected_log_text, expected_text_template, expected_keyboard_func, expected_photo_attr, expected_fsm_state",
    [
        # 1. Переход к выбору материалов для баннеров
        (2, "banners", None, {}, "CLICK: banners", BANNERS_MESSAGE_TEXT, get_banner_materials_keyboard, "BANNERS_PHOTO_PATH", None),
        # 2. Выбор конкретного материала
        (3, "select_material", "frontlit_440", {}, "CLICK: select_material (item: frontlit_440)", MATERIAL_SELECTED_TEXT.format(material_name=MATERIAL_NAME_MAP["frontlit_440"]), lambda: get_back_button_keyboard(2, "back_to_materials"), "BANNERS_PHOTO_PATH", OrderState.entering_size),
        # 3. Возврат к выбору категорий
        (1, "back_to_products", None, {}, "CLICK: back_to_products", CATALOG_MESSAGE_TEXT, get_catalog_keyboard, "CATALOG_PHOTO_PATH", None),
        # 4. Выбор качества печати (требует начального состояния)
        (4, "select_quality", "720", {"material_name": "Test Material", "width": 3.0, "height": 2.0}, "CLICK: select_quality (item: 720)", PROMPT_FOR_PROCESSING_TEXT.format(material_name="Test Material", width=3.0, height=2.0, quality="720"), get_processing_type_keyboard, "BANNERS_PHOTO_PATH", OrderState.choosing_processing_type),
    ]
)
@patch("app.handlers.user_handlers.log_query", new_callable=AsyncMock)
@patch("app.handlers.user_handlers._update_calculator_widget", new_callable=AsyncMock)
@patch("app.handlers.user_handlers.settings")
async def test_navigate_catalog(
    mock_settings, mock_update_widget, mock_log,
    mock_bot, mock_callback_query: CallbackQuery, mock_fsm_context: FSMContext,
    level, action, item_id, initial_state_data, expected_log_text, expected_text_template,
    expected_keyboard_func, expected_photo_attr, expected_fsm_state
):
    """Тестирует ключевые переходы в воронке продаж через обработчик navigate_catalog."""
    # --- Настройка ---
    # 1. Устанавливаем начальное состояние FSM, если оно необходимо для теста
    if initial_state_data:
        await mock_fsm_context.update_data(**initial_state_data)

    # 2. Формируем данные для callback
    callback_data = CatalogCallback(level=level, action=action, item_id=item_id)
    mock_callback_query.data = callback_data.pack()

    # 3. Устанавливаем мок для пути к фото
    setattr(mock_settings, expected_photo_attr, f"fake/path/{expected_photo_attr}.jpg")

    # --- Вызов ---
    await user_handlers.navigate_catalog(mock_callback_query, callback_data, mock_fsm_context, mock_bot)

    # --- Проверки ---
    # 1. Проверка подтверждения callback
    mock_callback_query.answer.assert_awaited_once()

    # 2. Проверка логирования
    mock_log.assert_called_once_with(
        user_id=mock_callback_query.from_user.id,
        username=mock_callback_query.from_user.username,
        first_name=mock_callback_query.from_user.first_name,
        last_name=mock_callback_query.from_user.last_name,
        query_text=expected_log_text,
    )

    # 3. Проверка обновления виджета
    mock_update_widget.assert_called_once()
    _, kwargs = mock_update_widget.call_args
    assert kwargs["state"] == mock_fsm_context
    assert kwargs["bot"] == mock_bot
    assert kwargs["chat_id"] == mock_callback_query.message.chat.id
    assert kwargs["text"] == expected_text_template
    # Сравниваем результат вызова функции клавиатуры, а не саму функцию
    assert kwargs["reply_markup"].model_dump_json() == expected_keyboard_func().model_dump_json()
    assert kwargs["photo_path"] == getattr(mock_settings, expected_photo_attr)

    # 4. Проверка установки состояния FSM
    current_state = await mock_fsm_context.get_state()
    assert current_state == (expected_fsm_state.state if expected_fsm_state else None)

    # 5. Проверка обновления данных в FSM (для шага выбора материала)
    if action == "select_material":
        state_data = await mock_fsm_context.get_data()
        assert state_data["material_id"] == item_id
        assert state_data["material_name"] == MATERIAL_NAME_MAP[item_id]


@pytest.mark.parametrize(
    "input_text, expected_width, expected_height, is_valid",
    [
        # Standard 'x' delimiter tests
        ("3 x 2", 3.0, 2.0, True),          # Basic case
        ("3.5 X 2,1", 3.5, 2.1, True),      # Uppercase X and comma
        ("10x5", 10.0, 5.0, True),          # No spaces
        ("  1,5 x 2.0  ", 1.5, 2.0, True),  # Extra spaces and comma
        # New '*' delimiter tests
        ("4 * 2", 4.0, 2.0, True),          # With spaces
        ("5.5*1", 5.5, 1.0, True),          # Without spaces
        # New 'на' delimiter tests
        ("6 на 3", 6.0, 3.0, True),        # With spaces
        ("7,2 НА 1.1", 7.2, 1.1, True),      # Uppercase and mixed separators
        ("invalid input", None, None, False),
        ("3x", None, None, False),
        ("x2", None, None, False),
    ]
)
@patch("app.handlers.user_handlers._update_calculator_widget", new_callable=AsyncMock)
@patch("app.handlers.user_handlers.settings")
async def test_handle_size_input(
    mock_settings, mock_update_widget,
    mock_bot, mock_message, mock_fsm_context: FSMContext,
    input_text, expected_width, expected_height, is_valid
):
    """Тестирует обработчик ввода размера баннера."""
    # --- Настройка ---
    mock_message.text = input_text
    mock_settings.BANNERS_PHOTO_PATH = "fake/path/banners.jpg"

    # Устанавливаем начальное состояние FSM
    await mock_fsm_context.set_state(OrderState.entering_size)
    await mock_fsm_context.update_data(
        calculator_message_id=12345,
        material_id="frontlit_440",
        material_name="Стандартный, 440 г/м²"
    )

    # --- Вызов ---
    await user_handlers.handle_size_input(mock_message, mock_fsm_context, mock_bot)

    # --- Проверки ---
    mock_message.delete.assert_called_once() # Сообщение пользователя должно быть удалено

    if is_valid:
        # Проверка установки состояния FSM
        assert await mock_fsm_context.get_state() == OrderState.choosing_print_quality.state

        # Проверка обновления данных в FSM
        state_data = await mock_fsm_context.get_data()
        assert state_data["width"] == expected_width
        assert state_data["height"] == expected_height
        assert state_data["material_name"] == "Стандартный, 440 г/м²"

        # Проверка вызова _update_calculator_widget
        mock_update_widget.assert_called_once()
        _, kwargs = mock_update_widget.call_args
        assert kwargs["text"] == PROMPT_FOR_QUALITY_TEXT.format(
            material_name="Стандартный, 440 г/м²",
            width=expected_width,
            height=expected_height
        )
        assert kwargs["reply_markup"].model_dump_json() == get_print_quality_keyboard().model_dump_json()
        assert kwargs["photo_path"] == mock_settings.BANNERS_PHOTO_PATH
        mock_message.reply.assert_not_called()
    else:
        # Если ввод невалидный, состояние FSM не должно меняться, и должно быть отправлено сообщение об ошибке
        assert await mock_fsm_context.get_state() == OrderState.entering_size.state
        mock_message.reply.assert_called_once()
        assert "Неверный формат" in mock_message.reply.call_args[0][0]
        mock_update_widget.assert_not_called()


@pytest.mark.parametrize(
    "initial_state, user_question",
    [
        (OrderState.entering_size, "Какой материал лучше для улицы?"),
        (OrderState.choosing_print_quality, "Что такое DPI?"),
        (OrderState.choosing_quantity, "Сколько будет стоить доставка?"),
    ]
)
@patch("app.handlers.user_handlers.process_query", new_callable=AsyncMock)
async def test_handle_question_in_funnel(
    mock_process_query,
    mock_bot, mock_message, mock_fsm_context: FSMContext,
    initial_state, user_question
):
    """
    Тестирует, что общие текстовые сообщения в воронке передаются в process_query,
    не прерывая FSM-состояние.
    """
    # --- Настройка ---
    mock_message.text = user_question
    await mock_fsm_context.set_state(initial_state)

    # --- Вызов ---
    await user_handlers.handle_question_in_funnel(mock_message, mock_bot, mock_fsm_context)

    # --- Проверки ---
    mock_process_query.assert_called_once_with(
        chat_id=mock_message.chat.id, user_question=user_question, bot=mock_bot, message_to_answer=mock_message, user=mock_message.from_user
    )
    # Убеждаемся, что состояние FSM не изменилось
    assert await mock_fsm_context.get_state() == initial_state.state


@pytest.mark.parametrize(
    "input_quantity, expected_quantity",
    [
        ("1", 1),
        ("10", 10),
        ("123", 123),
    ]
)
@patch("app.handlers.user_handlers._update_calculator_widget", new_callable=AsyncMock)
@patch("app.handlers.user_handlers.settings")
async def test_handle_quantity_input(
    mock_settings, mock_update_widget,
    mock_bot, mock_message, mock_fsm_context: FSMContext,
    input_quantity, expected_quantity
):
    """Тестирует обработчик ручного ввода количества."""
    # --- Настройка ---
    mock_message.text = input_quantity
    mock_settings.BANNERS_PHOTO_PATH = "fake/path/banners.jpg"

    # Устанавливаем начальное состояние FSM и данные, необходимые для форматирования текста
    await mock_fsm_context.set_state(OrderState.entering_quantity)
    await mock_fsm_context.update_data(
        calculator_message_id=12345,
        material_name="Test Material",
        width=3.0,
        height=2.0,
        quality="720",
        processing="Test Processing",
    )

    # --- Вызов ---
    await user_handlers.handle_quantity_input(mock_message, mock_fsm_context, mock_bot)

    # --- Проверки ---
    # 1. Сообщение пользователя должно быть удалено
    mock_message.delete.assert_called_once()

    # 2. Проверка обновления данных в FSM
    state_data = await mock_fsm_context.get_data()
    assert state_data["quantity"] == expected_quantity

    # 3. Проверка установки состояния FSM
    assert await mock_fsm_context.get_state() == OrderState.choosing_urgency.state

    # 4. Проверка вызова _update_calculator_widget
    mock_update_widget.assert_called_once()
    _, kwargs = mock_update_widget.call_args
    assert kwargs["state"] == mock_fsm_context
    assert kwargs["bot"] == mock_bot
    assert kwargs["chat_id"] == mock_message.chat.id
    assert kwargs["text"] == PROMPT_FOR_URGENCY_TEXT.format(
        material_name="Test Material",
        width=3.0,
        height=2.0,
        quality="720",
        processing="Test Processing",
        quantity=expected_quantity,
    )
    assert kwargs["reply_markup"].model_dump_json() == get_urgency_keyboard().model_dump_json()
    assert kwargs["photo_path"] == mock_settings.BANNERS_PHOTO_PATH




@pytest.mark.parametrize(
    "action_name, expected_log_text, handler_to_call",
    [
        ("restart", "CLICK: Restart Bot", "handle_start"),
        ("reset", "CLICK: Reset Chat", "handle_reset"),
    ]
)
@patch("app.handlers.user_handlers.log_query", new_callable=AsyncMock)
@patch("app.handlers.user_handlers.handle_start", new_callable=AsyncMock)
@patch("app.handlers.user_handlers.handle_reset", new_callable=AsyncMock)
async def test_handle_actions(
    mock_handle_reset, mock_handle_start, mock_log,
    mock_bot, mock_callback_query: CallbackQuery, mock_fsm_context: FSMContext,
    action_name, expected_log_text, handler_to_call
):
    """Тестирует обработчик общих действий (restart, reset) из меню помощи."""
    # --- Настройка ---
    callback_data = ActionCallback(name=action_name)
    mock_callback_query.data = callback_data.pack()

    # --- Вызов ---
    await user_handlers.handle_actions(mock_callback_query, callback_data, mock_bot, mock_fsm_context)

    # --- Проверки ---
    mock_callback_query.answer.assert_awaited_once()

    mock_log.assert_called_once_with(
        user_id=mock_callback_query.from_user.id,
        username=mock_callback_query.from_user.username,
        first_name=mock_callback_query.from_user.first_name,
        last_name=mock_callback_query.from_user.last_name,
        query_text=expected_log_text,
    )

    if handler_to_call == "handle_start":
        mock_handle_start.assert_called_once_with(mock_callback_query.message, mock_fsm_context, mock_bot)
        mock_handle_reset.assert_not_called()
    elif handler_to_call == "handle_reset":
        mock_handle_reset.assert_called_once_with(mock_callback_query.message)
        mock_handle_start.assert_not_called()