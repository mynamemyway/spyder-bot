# tests/test_ui_commands.py

from unittest.mock import AsyncMock

import pytest
from aiogram import Bot
from aiogram.types import BotCommand

from app.ui_commands import set_ui_commands

# Mark all tests in this file as asyncio
pytestmark = pytest.mark.asyncio


async def test_set_ui_commands():
    """
    Tests that the set_ui_commands function correctly calls the
    bot.set_my_commands method with the expected list of BotCommand objects.
    """
    # 1. Create a mock Bot object
    mock_bot = AsyncMock(spec=Bot)

    # 2. Call the function to be tested
    await set_ui_commands(mock_bot)

    # 3. Define the expected list of commands
    expected_commands = [
        BotCommand(command="start", description="Начать / Перезапустить"),
        BotCommand(command="catalog", description="Каталог продукции"),
        BotCommand(command="reset", description="Сбросить контекст диалога"),
        BotCommand(command="help", description="Помощь"),
    ]

    # 4. Assert that the bot's method was called once with the correct arguments
    mock_bot.set_my_commands.assert_awaited_once_with(commands=expected_commands)