# tests/test_stats.py

import pytest
import aiosqlite

from app.core.stats import log_query

# Mark all tests in this file as asyncio
pytestmark = pytest.mark.asyncio


@pytest.fixture
def isolated_db_path(tmp_path, monkeypatch):
    """
    Pytest fixture that creates a temporary database file for test isolation.

    It uses pytest's built-in `tmp_path` fixture to create a temporary
    directory. A unique database file is created inside it for each test.
    `monkeypatch` is used to redirect the application's database path to this
    temporary file.

    Returns:
        The path to the temporary database file.
    """
    db_path = tmp_path / "test_db.sqlite3"
    monkeypatch.setattr("app.core.stats.CHAT_HISTORY_DB_PATH", str(db_path))
    return str(db_path)


async def test_log_query_full(isolated_db_path):
    """
    Tests the log_query function with a full set of arguments, simulating
    a query that involves the RAG chain and an LLM response.
    """
    user_id = 12345
    username = "testuser"
    first_name = "Test"
    last_name = "User"
    query_text = "What is RAG?"
    retrieved_context = "RAG stands for Retrieval-Augmented Generation."
    llm_response = "It's a technique to improve LLM responses."

    await log_query(
        user_id=user_id,
        username=username,
        first_name=first_name,
        last_name=last_name,
        query_text=query_text,
        retrieved_context=retrieved_context,
        llm_response=llm_response,
    )

    async with aiosqlite.connect(isolated_db_path) as db:
        cursor = await db.execute("SELECT * FROM query_stats")
        record = await cursor.fetchone()

    assert record is not None
    assert record[1] == user_id
    assert record[2] == username
    assert record[3] == first_name
    assert record[4] == last_name
    assert record[5] == query_text
    assert record[6] == retrieved_context
    assert record[7] == llm_response


async def test_log_query_minimal(isolated_db_path):
    """
    Tests the log_query function with only the required arguments, simulating
    a static button click that does not involve the RAG chain.
    """
    user_id = 54321
    username = "clickuser"
    query_text = "CLICK: Projects Button"

    await log_query(user_id=user_id, username=username, first_name=None, last_name=None, query_text=query_text)

    async with aiosqlite.connect(isolated_db_path) as db:
        cursor = await db.execute("SELECT * FROM query_stats")
        record = await cursor.fetchone()

    assert record is not None
    assert record[1] == user_id
    assert record[5] == query_text
    assert record[6] is None  # retrieved_context should be NULL
    assert record[7] is None  # llm_response should be NULL