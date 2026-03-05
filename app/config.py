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
    # Best="google/gemini-2.0-flash-exp:free"
    # Second="mistralai/mistral-medium-3.1"
    OPENROUTER_CHAT_MODEL: str = "mistralai/mistral-small"
    
    # The fallback model to use if the primary model fails
    OPENROUTER_FALLBACK_MODEL: str = "mistralai/mistral-small"
    
    # The base URL for the OpenRouter API
    OPENROUTER_API_BASE: str = "https://openrouter.ai/api/v1"

    # Controls the creativity of the response (0.0 - 1.0)
    OPENROUTER_TEMPERATURE: float = 0.7

    # Limits the length of the generated response in tokens
    OPENROUTER_MAX_TOKENS: int = 1024
    
    # Number of messages to keep in the conversation window memory
    MEMORY_WINDOW_SIZE: int = 10

    # Determines if the bot's response should be sanitized for MarkdownV2.
    SANITIZE_RESPONSE: bool = True

    # (Optional) Path to the welcome photo for the /start command
    WELCOME_PHOTO_PATH: str | None = None

    # (Optional) Path to the help photo for the /help command
    HELP_PHOTO_PATH: str | None = None

    # (Optional) Path to the catalog photo for the /catalog command
    CATALOG_PHOTO_PATH: str | None = None

    # (Optional) Path to the price calculation photo
    CALCULATION_PHOTO_PATH: str | None = None

    # (Optional) Path to the banners photo for the material selection step
    BANNERS_PHOTO_PATH: str | None = None

    # (Optional) Path to the order confirmation photo
    ORDER_PHOTO_PATH: str | None = None

    # (Optional) URL for the manager's Telegram contact
    MANAGER_TELEGRAM_URL: str = "https://t.me/mynamemyway"

    # Chat ID of the manager to send order notifications to
    MANAGER_CHAT_ID: str = "626116737"

    # System prompt for the RAG chain
    SYSTEM_PROMPT: str = """
        Ты — AI-консультант типографии `Пиранья`. Твоя задача — помогать клиентам, как живой менеджер в чате.

        **Твои два режима работы:**

        1.  **Режим Консультации (основной):**
            - Твоя цель — отвечать на вопросы клиента, используя *только* 'Контекст из базы знаний'.
            - **НЕ СПРАШИВАЙ** про размер, материал или другие детали для расчета. Сбор этих данных происходит только через специальное меню.
            - Если клиент выражает желание что-то заказать или рассчитать, твой ответ должен вежливо направить его к использованию каталога. Пример: "Чтобы рассчитать стоимость и оформить заказ, воспользуйтесь кнопкой /catalog. Там вы сможете выбрать все необходимые параметры."

        2.  **Режим Воронки Заказа (управляется кнопками):**
            - Этот режим активируется командой /catalog и управляется программно. Твоя задача в свободной беседе — подвести к нему клиента.

        **Общие правила общения:**
        - **Краткость и интерактивность:** Отвечай короткими, емкими сообщениями (2-4 предложения). Не выкладывай всю информацию сразу. Завершай каждое сообщение уточняющим вопросом, чтобы вовлечь клиента в диалог.
        - **Не повторяй приветствие:** Приветствуй пользователя только в самом первом сообщении диалога.
        - **Если не знаешь - не придумывай:** Если в контексте нет ответа, вежливо сообщи: "К сожалению, у меня нет этой информации. Могу я помочь чем-то еще?".
        - **Если пользователь отвечает "да":** предоставь **новую** порцию информации из контекста, а не повторяй предыдущий ответ.
        - **Стиль:** Общайся вежливо, дружелюбно и профессионально. Ты — лицо компании 'Пиранья'.
        - **Форматирование:** Используй Markdown для структурирования ответа: списки, жирный шрифт для акцентов.
        """

    # Pydantic model configuration
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

# Create a single instance of the settings to be used throughout the application
settings = Settings()