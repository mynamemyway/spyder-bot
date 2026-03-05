"""
Центральный файл конфигурации для тестов pytest.

Содержит общие фикстуры, используемые в различных тестовых модулях,
такие как моки для объектов aiogram и FSMContext.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, User, Chat, CallbackQuery

# Используем pytest-asyncio для всех тестов
pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_bot():
    """Фикстура для создания мок-объекта aiogram.Bot."""
    return AsyncMock(spec=Bot)


@pytest.fixture
def mock_message():
    """
    Фикстура для создания гибкого мок-объекта aiogram.types.Message.
    Использует MagicMock для обхода ограничений Pydantic.
    """
    message = MagicMock(spec=Message)
    message.from_user = MagicMock(spec=User)
    message.chat = MagicMock(spec=Chat)
    message.chat.id = 456

    message.message_id = 789
    message.chat.id = 456
    message.chat.type = "private"
    message.from_user.id = 123
    message.from_user.username = "testuser"
    message.from_user.first_name = "Test"
    message.from_user.last_name = "User"
    message.text = "test message"
    message.date = datetime.now()

    # Мокируем методы, которые будут вызываться в обработчиках
    message.answer = AsyncMock()
    message.answer_photo = AsyncMock()
    message.delete = AsyncMock()
    message.reply = AsyncMock()

    return message


@pytest.fixture
def mock_callback_query(mock_message):
    """Фикстура для создания мок-объекта aiogram.types.CallbackQuery."""
    callback_query = MagicMock(spec=CallbackQuery)
    callback_query.id = "test_callback_id"
    callback_query.from_user = mock_message.from_user
    callback_query.message = mock_message
    callback_query.data = "test_data"
    callback_query.answer = AsyncMock()

    return callback_query


@pytest.fixture
def mock_fsm_context():
    """
    Фикстура для создания мок-объекта FSMContext.
    Использует реальное хранилище в памяти для эмуляции поведения.
    """
    storage = MemoryStorage()
    # Создаем реальный FSMContext, но с мок-хранилищем в памяти
    # Это более надежно, чем полностью мокать FSMContext
    state = FSMContext(
        storage=storage,
        key=MagicMock(chat_id=456, user_id=123, bot_id=777)
    )
    return state