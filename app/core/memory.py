# app/core/memory.py

import json
from pathlib import Path

import aiosqlite
from langchain.memory import ConversationBufferWindowMemory
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import (
    BaseMessage,
    _message_from_dict,
    message_to_dict,
)

from app.config import settings

# --- Constants ---

# Define the root directory of the project.
# Path(__file__) is the path to the current file (app/core/memory.py).
# .parent.parent navigates up two levels to the project root.
ROOT_DIR = Path(__file__).parent.parent.parent

# Directory for databases.
DB_DIR = ROOT_DIR / "app" / "db"

# Path to the SQLite database file for storing chat history.
CHAT_HISTORY_DB_PATH = DB_DIR / "chat_history.sqlite3"


# --- Chat History Store ---

class SQLiteChatMessageHistory(BaseChatMessageHistory):
    """
    Chat message history stored in a SQLite database.

    This class provides an async interface to store, retrieve, and manage
    chat messages, conforming to the LangChain's BaseChatMessageHistory interface.
    """

    def __init__(self, session_id: str, db_path: str = str(CHAT_HISTORY_DB_PATH)):
        """
        Initializes the chat history store for a specific session.

        Args:
            session_id: A unique identifier for the chat session.
            db_path: The file path to the SQLite database.
        """
        self.db_path = db_path
        self.session_id = session_id

    async def _create_table_if_not_exists(self) -> None:
        """
        Asynchronously creates the 'chat_history' table if it doesn't exist.
        The table stores session ID and the serialized message content.
        """
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    message TEXT NOT NULL
                );
                """
            )
            await db.commit()

    @property
    async def messages(self) -> list[BaseMessage]:
        """
        Asynchronously retrieve all messages for the current session from the database.

        Returns:
            A list of BaseMessage objects, ordered by their insertion time.
        """
        await self._create_table_if_not_exists()
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT message FROM chat_history WHERE session_id = ? ORDER BY id ASC",
                (self.session_id,),
            )
            rows = await cursor.fetchall()
            if not rows:
                return []

            # Deserialize JSON strings back into LangChain message objects
            return [_message_from_dict(json.loads(row[0])) for row in rows]

    async def add_message(self, message: BaseMessage) -> None:
        """
        Asynchronously adds a new message to the history for the current session.

        Args:
            message: The BaseMessage object to add.
        """
        await self._create_table_if_not_exists()
        # Serialize the LangChain message object to a JSON string
        serialized_message = json.dumps(message_to_dict(message), ensure_ascii=False)

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO chat_history (session_id, message) VALUES (?, ?)",
                (self.session_id, serialized_message),
            )
            await db.commit()

    async def add_messages(self, messages: list[BaseMessage]) -> None:
        """
        Asynchronously adds a list of messages to the history for the current session.

        This method is optimized for batch insertion using `executemany`.

        Args:
            messages: A list of BaseMessage objects to add.
        """
        if not messages:
            return

        await self._create_table_if_not_exists()

        # Serialize all messages and prepare them for batch insertion
        serialized_messages = [
            (self.session_id, json.dumps(message_to_dict(msg), ensure_ascii=False))
            for msg in messages
        ]

        async with aiosqlite.connect(self.db_path) as db:
            await db.executemany(
                "INSERT INTO chat_history (session_id, message) VALUES (?, ?)",
                serialized_messages,
            )
            await db.commit()

    async def clear(self) -> None:
        """
        Asynchronously clears all message history for the current session.
        """
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "DELETE FROM chat_history WHERE session_id = ?", (self.session_id,)
            )
            await db.commit()


# --- Memory Factory ---

def get_chat_memory(session_id: str) -> ConversationBufferWindowMemory:
    """
    Factory function to create and return a memory object for a given session.

    This function encapsulates the creation of a chat history store and
    wires it into a LangChain memory object with a fixed-size window.

    Args:
        session_id: The unique identifier for the chat session.

    Returns:
        An instance of ConversationBufferWindowMemory configured with
        SQLite-backed history.
    """
    chat_history = SQLiteChatMessageHistory(session_id=session_id)

    return ConversationBufferWindowMemory(
        chat_memory=chat_history,
        k=settings.MEMORY_WINDOW_SIZE,
        return_messages=True,
        memory_key="chat_history",  # Key for chain integration
    )