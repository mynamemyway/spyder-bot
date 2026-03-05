# main.py

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

from app.config import settings
from app.handlers import user_handlers
from app.ui_commands import set_ui_commands


class TelemetryFilter(logging.Filter):
    """
    A custom logging filter to suppress noisy telemetry errors from ChromaDB.
    """
    def filter(self, record: logging.LogRecord) -> bool:
        # Suppress logs from ChromaDB's telemetry module
        return not record.name.startswith("chromadb.telemetry.product.posthog")


async def main() -> None:
    """
    Initializes and starts the Telegram bot.
    This function sets up the bot and dispatcher, registers handlers (in the future),
    and starts polling for updates from Telegram.
    """
    # Configure logging first to ensure handlers and filters are set up correctly.
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)

    # Add the custom filter to the root logger to suppress ChromaDB telemetry errors
    telemetry_filter = TelemetryFilter()
    # Apply the filter to all existing handlers of the root logger.
    for handler in logging.getLogger().handlers:
        handler.addFilter(telemetry_filter)

    # Initialize Bot and Dispatcher instances. The bot token is read from the settings.
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode="Markdown"),
    )
    dp = Dispatcher()

    # Include the router in the dispatcher. This registers all handlers from the router.
    dp.include_router(user_handlers.router)

    # Set the bot's UI commands (e.g., /start, /help) in the Telegram menu.
    await set_ui_commands(bot)

    # Start the polling process to receive updates from Telegram.
    # This will run indefinitely until the process is stopped.
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())