# app/core/chain.py

import textwrap
import logging
from operator import itemgetter
from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from langchain_openai import ChatOpenAI

from app.config import settings
from app.core.memory import get_chat_memory
from app.core.rag import get_vector_store

# --- Fallback Logging ---


class FallbackLoggingCallbackHandler(BaseCallbackHandler):
    """A custom callback handler to log when the primary LLM fails and a fallback is used."""

    async def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Asynchronously handles LLM errors, logging the failure and the switch to a fallback model.
        This method is triggered automatically by the LangChain framework on an LLM error.
        """
        logging.warning(
            f"Primary LLM failed with error: {error}. Run ID: {run_id}"
        )
        logging.info(
            f"Switching to fallback model: {settings.OPENROUTER_FALLBACK_MODEL}"
        )

# --- Chain Creation ---


async def _get_async_chat_history(x: dict) -> dict:
    """
    Asynchronously loads chat history directly from SQLiteChatMessageHistory
    and applies windowing logic.

    This is necessary because LangChain's ConversationBufferWindowMemory
    is not fully async-aware for its `chat_memory` attribute's `messages` property,
    leading to `TypeError` when trying to access an awaited coroutine.
    """
    session_id = x["session_id"]
    # Get the ConversationBufferWindowMemory instance, which wraps SQLiteChatMessageHistory
    memory_buffer = get_chat_memory(session_id=session_id)
    # Await the async messages property of the underlying SQLiteChatMessageHistory
    all_messages = await memory_buffer.chat_memory.messages
    # Apply windowing logic (k * 2 messages for k conversation turns)
    k = settings.MEMORY_WINDOW_SIZE
    windowed_messages = all_messages[-k * 2 :] if k > 0 else []
    return {"chat_history": windowed_messages}

def get_rag_chain():
    """
    Creates and returns a conversational RAG (Retrieval-Augmented Generation) chain.

    This function orchestrates the entire process of handling a user query:
    1.  Loads conversation history for the session.
    2.  Retrieves relevant documents (context) from the vector store based on the question.
    3.  Formats the system prompt with the retrieved context.
    4.  Sends the prompt, history, and question to the LLM.
    5.  Parses the LLM's response into a string.
    6.  Saves the new question and answer to the session's history.

    Returns:
        A Runnable object representing the complete conversational RAG chain.
    """
    # 1. Initialize components
    # Initialize the primary LLM using the main model from settings
    primary_llm = ChatOpenAI(
        model=settings.OPENROUTER_CHAT_MODEL,
        openai_api_key=settings.OPENROUTER_API_KEY,
        base_url=settings.OPENROUTER_API_BASE,
        temperature=settings.OPENROUTER_TEMPERATURE,  # Controls the creativity of the response
        max_tokens=settings.OPENROUTER_MAX_TOKENS,  # Limits the length of the generated response
    )

    # Initialize the fallback LLM using the backup model from settings
    fallback_llm = ChatOpenAI(
        model=settings.OPENROUTER_FALLBACK_MODEL,
        openai_api_key=settings.OPENROUTER_API_KEY,
        base_url=settings.OPENROUTER_API_BASE,
        temperature=settings.OPENROUTER_TEMPERATURE,
        max_tokens=settings.OPENROUTER_MAX_TOKENS,
    )

    # Create a resilient LLM component with a fallback mechanism
    llm = primary_llm.with_fallbacks([fallback_llm])

    retriever = get_vector_store().as_retriever()

    # 2. Define the prompt template
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", textwrap.dedent(settings.SYSTEM_PROMPT).strip()),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "Вопрос: {question}\n\nКонтекст из базы знаний:\n{context}"),
        ]
    )

    # 3. Define a function to format retrieved documents
    def format_docs(docs):
        """Converts a list of Document objects into a single string."""
        return "\n\n".join(doc.page_content for doc in docs)

    # 4. Create the core RAG chain using LangChain Expression Language (LCEL)
    # This chain is responsible for retrieving context and generating a response.
    # It now returns a dictionary with the answer and the retrieved context.
    rag_chain = (
        prompt | llm | StrOutputParser()
    )

    # 5. Create the full conversational chain with memory
    # This chain takes a session_id and a question as input.
    conversational_rag_chain = (
        # Step 1: Prepare the context in parallel: load chat history and retrieve documents.
        # The result is a dictionary with 'chat_history' and 'context'.
        RunnablePassthrough.assign(
            chat_history=RunnableLambda(_get_async_chat_history) | itemgetter("chat_history"),
            context=itemgetter("question") | retriever | format_docs
        )
        # Step 2: Pass the prepared context to the main RAG chain to get the answer.
        # We use assign again to add the 'answer' to the dictionary.
        | RunnablePassthrough.assign(answer=rag_chain)
        # Step 3: Select only the 'answer' and 'context' keys for the final output.
        # This ensures a clean, predictable output format.
        | (lambda x: {"answer": x["answer"], "context": x["context"]})
    )

    return conversational_rag_chain