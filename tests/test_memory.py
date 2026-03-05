# tests/test_memory.py

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.core.memory import SQLiteChatMessageHistory

# Mark all tests in this file as asyncio
pytestmark = pytest.mark.asyncio


@pytest.fixture
def isolated_db_path(tmp_path, monkeypatch):
    """
    Pytest fixture that creates a temporary database file for test isolation.
    It patches the database path in the `memory` module.
    """
    db_path = tmp_path / "test_chat_history.sqlite3"
    monkeypatch.setattr("app.core.memory.CHAT_HISTORY_DB_PATH", str(db_path))
    return str(db_path)


async def test_add_and_retrieve_single_message(isolated_db_path):
    """Tests adding and retrieving a single message."""
    session_id = "session_1"
    history = SQLiteChatMessageHistory(session_id=session_id, db_path=isolated_db_path)

    # Add a single message
    message = HumanMessage(content="Hello")
    await history.add_message(message)

    # Retrieve messages
    retrieved_messages = await history.messages
    assert len(retrieved_messages) == 1
    assert retrieved_messages[0].content == "Hello"
    assert isinstance(retrieved_messages[0], HumanMessage)


async def test_add_and_retrieve_multiple_messages(isolated_db_path):
    """Tests adding and retrieving multiple messages using add_messages."""
    session_id = "session_2"
    history = SQLiteChatMessageHistory(session_id=session_id, db_path=isolated_db_path)

    messages = [
        HumanMessage(content="First question"),
        AIMessage(content="First answer"),
    ]
    await history.add_messages(messages)

    retrieved_messages = await history.messages
    assert len(retrieved_messages) == 2
    assert retrieved_messages[0].content == "First question"
    assert retrieved_messages[1].content == "First answer"


async def test_clear_history(isolated_db_path):
    """Tests that clearing the history removes all messages for a session."""
    session_id = "session_3"
    history = SQLiteChatMessageHistory(session_id=session_id, db_path=isolated_db_path)

    # Add a message and verify it's there
    await history.add_message(HumanMessage(content="This will be cleared"))
    assert len(await history.messages) == 1

    # Clear the history
    await history.clear()

    # Verify the history is empty
    assert len(await history.messages) == 0


async def test_history_isolation_between_sessions(isolated_db_path):
    """
    Tests that message histories for different sessions are isolated.
    """
    session_id_a = "session_A"
    session_id_b = "session_B"

    history_a = SQLiteChatMessageHistory(session_id=session_id_a, db_path=isolated_db_path)
    history_b = SQLiteChatMessageHistory(session_id=session_id_b, db_path=isolated_db_path)

    # Add messages to both sessions
    await history_a.add_message(HumanMessage(content="Message for A"))
    await history_b.add_message(HumanMessage(content="Message for B"))

    # Retrieve and verify messages for session A
    messages_a = await history_a.messages
    assert len(messages_a) == 1
    assert messages_a[0].content == "Message for A"

    # Retrieve and verify messages for session B
    messages_b = await history_b.messages
    assert len(messages_b) == 1
    assert messages_b[0].content == "Message for B"

    # Clear session A and verify it doesn't affect session B
    await history_a.clear()
    assert len(await history_a.messages) == 0
    assert len(await history_b.messages) == 1


async def test_non_ascii_characters(isolated_db_path):
    """
    Tests that non-ASCII characters (like Cyrillic) are stored and
    retrieved correctly.
    """
    session_id = "session_cyrillic"
    history = SQLiteChatMessageHistory(session_id=session_id, db_path=isolated_db_path)

    cyrillic_message = "Привет, мир!"
    message = HumanMessage(content=cyrillic_message)
    await history.add_message(message)

    retrieved_messages = await history.messages
    assert len(retrieved_messages) == 1
    assert retrieved_messages[0].content == cyrillic_message