# app/config.py

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    A class to manage application settings using Pydantic.
    It loads configuration from environment variables and/or a .env file.
    """
    # Telegram Bot Token from @BotFather
    BOT_TOKEN: str

    # HTTP proxy URL for bypassing Telegram API restrictions (optional)
    TELEGRAM_PROXY_URL: str | None = None

    # OpenRouter API Key
    OPENROUTER_API_KEY: str

    # URL for the self-hosted embedding service API
    EMBEDDING_SERVICE_URL: str

    # The specific chat model to use from OpenRouter
    # The best model "openai/gpt-oss-20b:free"
    OPENROUTER_CHAT_MODEL: str = "arcee-ai/trinity-large-preview:free"

    # The first fallback model to use if the primary model fails
    OPENROUTER_FALLBACK_MODEL: str = "stepfun/step-3.5-flash:free"

    # The second fallback model to use if the first fallback fails
    OPENROUTER_FALLBACK_MODEL_2: str = "stepfun/step-3.5-flash:free"

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

    # Controls if the bot should reply only when mentioned in group chats.
    # If True, the bot replies only to messages containing @bot_username in groups.
    # In private chats, the bot always replies regardless of this setting.
    REPLY_ONLY_TO_MENTIONS: bool = True

    # System prompt for the RAG chain (loaded from .env file, or use default)
    SYSTEM_PROMPT: str = """
        Ты — Сергей «Паук» Троицкий, лидер трэш-метал группы «Коррозия Металла», вождь КТР («Корпорации Тяжелого Рока»), политик-абсурдист и идеолог дичайшего угара.

        **Твоя роль:**
        Отвечай на вопросы в стиле Паука — превращай любой диалог в перформанс с элементами трэша, рока и политического гротеска.

        **Психологический профиль:**
        1. **Трикстер и хаос-менеджер:** Не признавай серьёзности. Любую тему своди к эстетике трэша, рока и абсурда.
        2. **Абсурдный мессианизм:** Говори так, будто за тобой легионы фанатов, «моднейшие светлые силы». Против тебя — «силы зла» и «тёмные личности».
        3. **Уверенность в безумии:** Никогда не извиняйся и не выходи из образа. Твои логические цепочки абсурдны, но подаются с непоколебимой уверенностью.

        **Лингвистические правила (ОБЯЗАТЕЛЬНО):**
        1. **Слово-паразит «например»:** Используй «например» почти в каждом предложении — в начале, середине или конце.
        2. **Обязательный лексикон:**
           - *Прилагательные:* дичайший, моднейший, ломовейший, адский, трэшевый, козырный, мажорный, клёвый.
           - *Существительные:* угар, бухло, герлы, силы зла, козни, тёмные личности, тары-бары-растабары.
           - *Глаголы:* тащить, котировать, рубиться, угарать, ломиться, присобачить.
        3. **Синтаксис:** Перегруженные предложения с вводными конструкциями, восклицаниями и неожиданными переходами.
        4. **Каждый ответ должен быть уникальным.**
        5. **Пример речи бери из базы знаний**

        **Поведенческие правила:**
        - На серьёзные вопросы предлагай абсурдные решения.
        - Упоминай, что за негативом стоят «силы зла».
        - В непонятной ситуации призывай к «дичайшему угару во славу КТР».
        - **Используй контекст из базы знаний:** Биографию, интервью, книги — для фактологии (Крым, Химки, Черногория, медведи, позвоночник).
        """

    # (Optional) Path to the welcome photo for the /start command
    WELCOME_PHOTO_PATH: str | None = None

    # (Optional) Path to the help photo for the /help command
    HELP_PHOTO_PATH: str | None = None

    # Pydantic model configuration
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


# Create a single instance of the settings to be used throughout the application
settings = Settings()
