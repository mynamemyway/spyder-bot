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
    """
    # Configure logging first to ensure handlers and filters are set up correctly.
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)

    # Add the custom filter to the root logger to suppress ChromaDB telemetry errors
    telemetry_filter = TelemetryFilter()
    for handler in logging.getLogger().handlers:
        handler.addFilter(telemetry_filter)

    # Create aiohttp session with proxy if configured
    if settings.TELEGRAM_PROXY_URL:
        from aiogram.client.session.aiohttp import AiohttpSession
        session = AiohttpSession(proxy=settings.TELEGRAM_PROXY_URL)
        bot = Bot(
            token=settings.BOT_TOKEN,
            default=DefaultBotProperties(parse_mode="Markdown"),
            session=session,
        )
        logging.info("Bot started with proxy: %s", settings.TELEGRAM_PROXY_URL)
    else:
        bot = Bot(
            token=settings.BOT_TOKEN,
            default=DefaultBotProperties(parse_mode="Markdown"),
        )
        logging.info("Bot started without proxy")

    dp = Dispatcher()

    # Include the router in the dispatcher.
    dp.include_router(user_handlers.router)

    # Set the bot's UI commands (e.g., /start, /help) in the Telegram menu.
    await set_ui_commands(bot)

    # Start the polling process to receive updates from Telegram.
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())