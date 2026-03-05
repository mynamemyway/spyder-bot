# app/config.py

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    A class to manage application settings using Pydantic.
    It loads configuration from environment variables and/or a .env file.
    """
    # Telegram Bot Token from @BotFather
    BOT_TOKEN: str

    # OpenRouter API Key
    OPENROUTER_API_KEY: str

    # URL for the self-hosted embedding service API
    EMBEDDING_SERVICE_URL: str

    # The specific chat model to use from OpenRouter
    OPENROUTER_CHAT_MODEL: str = "openai/gpt-oss-20b:free"

    # The fallback model to use if the primary model fails
    OPENROUTER_FALLBACK_MODEL: str = "arcee-ai/trinity-large-preview:free"

    # The base URL for the OpenRouter API
    OPENROUTER_API_BASE: str = "https://openrouter.ai/api/v1"

    # Controls the creativity of the response (0.0 - 1.0)
    OPENROUTER_TEMPERATURE: float = 1

    # Limits the length of the generated response in tokens
    OPENROUTER_MAX_TOKENS: int = 1024

    # Number of messages to keep in the conversation window memory
    MEMORY_WINDOW_SIZE: int = 10

    # Determines if the bot's response should be sanitized for Markdown.
    SANITIZE_RESPONSE: bool = True

    # (Optional) URL for the manager's Telegram contact
    MANAGER_TELEGRAM_URL: str = "https://t.me/mynamemyway"

    # System prompt for the RAG chain
    SYSTEM_PROMPT: str = """
        Ты — полезный AI-ассистент. Твоя задача — помогать пользователям, отвечая на их вопросы.

        **Правила общения:**
        - **Используй контекст:** Отвечай на вопросы, используя *только* предоставленный 'Контекст из базы знаний'.
        - **Не придумывай:** Если в контексте нет ответа, вежливо сообщи, что не обладаешь этой информацией.
        - **Будь краток:** Отвечай ёмко и по делу (2-4 предложения).
        - **Стиль:** Общайся вежливо, дружелюбно и профессионально.
        - **Форматирование:** Используй Markdown для структурирования ответа: списки, жирный шрифт для акцентов.
        """

    # (Optional) Path to the welcome photo for the /start command
    WELCOME_PHOTO_PATH: str | None = None

    # (Optional) Path to the help photo for the /help command
    HELP_PHOTO_PATH: str | None = None

    # Pydantic model configuration
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


# Create a single instance of the settings to be used throughout the application
settings = Settings()
