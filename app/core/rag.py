# app/core/rag.py

import asyncio
import sys
import logging
import httpx
from typing import List, Any
import time

from langchain_community.document_loaders import TextLoader # Keep for now, will be replaced later
from langchain_core.embeddings import Embeddings
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma

from app.config import settings

from pathlib import Path

# --- Constants ---

# Define the root directory of the project.
# Path(__file__) is the path to the current file (app/core/rag.py).
# .parent.parent.parent navigates up three levels to the project root.
ROOT_DIR = Path(__file__).parent.parent.parent

# Directory for the knowledge base source documents.
# The knowledge base is located within the 'app' directory.
KNOWLEDGE_BASE_DIR = Path(__file__).parent.parent / "knowledge_base"

# Directory where the local ChromaDB vector store will be persisted.
CHROMA_PERSIST_DIR = ROOT_DIR / "chroma_db"

# --- Batching Constants for Indexing ---
EMBEDDING_BATCH_SIZE = 16  # Number of documents to process in one batch
EMBEDDING_BATCH_DELAY = 1  # Delay in seconds between batches


# --- Custom Embedding Client ---

class ApiServiceEmbeddings(Embeddings):
    """
    Custom LangChain embedding class that connects to a self-hosted embedding service.

    This class handles the communication with the FastAPI service, sending text
    and receiving vector embeddings. It implements the LangChain `Embeddings`
    interface, making it compatible with ChromaDB and other components.
    """

    def __init__(self, api_url: str, async_client: httpx.AsyncClient, loop: asyncio.AbstractEventLoop):
        """
        Initializes the embedding service client.

        Args:
            api_url: The full URL of the `/embed` endpoint.
            async_client: An instance of httpx.AsyncClient for making API calls.
            loop: The running asyncio event loop.
        """
        self.api_url = api_url
        self.async_client = async_client
        self.loop = loop

    async def _send_request(self, texts: List[str]) -> List[List[float]]:
        """Sends a request to the embedding API and processes the response."""
        try:
            response = await self.async_client.post(
                self.api_url, json={"texts": texts}, timeout=60.0
            )
            response.raise_for_status()  # Raise an exception for 4xx or 5xx status codes
            data = response.json()
            return data["embeddings"]
        except httpx.HTTPStatusError as e:
            logging.error(f"HTTP error occurred: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logging.error(f"An error occurred while calling the embedding API: {e}")
            raise

    async def aembed_documents(self, texts: List[str]) -> List[List[float]]:
        """Asynchronously generates embeddings for a list of documents."""
        return await self._send_request(texts)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Generates embeddings for a list of documents in a synchronous context.

        This method is a thread-safe bridge to the async version. It submits
        the async task to the running event loop from the current thread
        (which is likely a worker thread from ChromaDB's executor) and waits
        for the result.
        """
        future = asyncio.run_coroutine_threadsafe(self.aembed_documents(texts), self.loop)
        return future.result()

    async def aembed_query(self, text: str) -> List[float]:
        """Asynchronously generates an embedding for a single query text."""
        embeddings = await self._send_request([text])
        return embeddings[0]

    def embed_query(self, text: str) -> List[float]:
        """
        Generates an embedding for a single query in a synchronous context.
        This is a sync-over-async bridge for compatibility.
        """
        future = asyncio.run_coroutine_threadsafe(self.aembed_query(text), self.loop)
        return future.result()


# --- Embedding Model Initialization ---

def get_embedding_model() -> Embeddings:
    """Initializes and returns the embedding model client."""
    # This function assumes it's called within a context where an event
    # loop is running, which is true for our `create_vector_store` script.
    loop = asyncio.get_running_loop()
    # Configure a transport with retry logic for transient errors (e.g., 429, 5xx)
    transport = httpx.AsyncHTTPTransport(retries=5)
    async_client = httpx.AsyncClient(transport=transport)

    embeddings = ApiServiceEmbeddings(api_url=settings.EMBEDDING_SERVICE_URL, async_client=async_client, loop=loop)
    return embeddings


# --- Vector Store Initialization ---

def get_vector_store() -> Chroma:
    """
    Initializes and returns the Chroma vector store.

    It uses the embedding model created by get_embedding_model and sets up
    a persistent directory to save the database on disk.
    """
    embeddings = get_embedding_model()
    vector_store = Chroma(
        persist_directory=str(CHROMA_PERSIST_DIR), embedding_function=embeddings
    )
    return vector_store


# --- Main Indexing Function ---

async def create_vector_store():
    """
    Orchestrates the entire process of creating the vector store:
    1. Loads and splits documents from the knowledge base.
    2. Initializes the vector store.
    3. Adds the documents to the store, triggering vectorization.
    """
    logging.info("Starting to create vector store...")

    # 1. Load and split documents
    chunked_documents = _load_and_split_documents()

    if not chunked_documents:
        logging.warning(
            "No documents found or processed. Vector store not created."
        )
        return

    logging.info(f"Loaded and split {len(chunked_documents)} document chunks.")

    # 2. Get the vector store instance
    vector_store = get_vector_store()

    # 3. Add documents to the vector store in batches to avoid rate limiting
    logging.info("Adding documents to the vector store in batches...")
    total_chunks = len(chunked_documents)
    num_batches = (total_chunks + EMBEDDING_BATCH_SIZE - 1) // EMBEDDING_BATCH_SIZE

    for i in range(0, total_chunks, EMBEDDING_BATCH_SIZE):
        batch = chunked_documents[i:i + EMBEDDING_BATCH_SIZE]
        batch_num = (i // EMBEDDING_BATCH_SIZE) + 1
        logging.info(f"Processing batch {batch_num}/{num_batches}...")

        await vector_store.aadd_documents(documents=batch)

        # Add a delay between batches to avoid rate limiting, but not after the last batch
        if i + EMBEDDING_BATCH_SIZE < total_chunks:
            logging.info(
                f"Waiting for {EMBEDDING_BATCH_DELAY} second(s) before next batch..."
            )
            await asyncio.sleep(EMBEDDING_BATCH_DELAY)

    logging.info("Vector store created and documents indexed successfully.")


# --- Document Loading and Splitting ---

def _load_and_split_documents() -> List[Document]:
    """
    Loads documents from the knowledge base directory and splits them into
    manageable chunks for vectorization.

    Returns:
        A list of Document objects, each representing a chunk.
    """
    # Pre-flight check to ensure the knowledge base directory exists.
    if not KNOWLEDGE_BASE_DIR.is_dir():
        logging.error(f"Knowledge base directory not found: '{KNOWLEDGE_BASE_DIR}'")
        logging.error("Please create it and add your markdown documents before running the script.")
        return []

    # 1. Find and load all markdown documents from the directory
    md_files = list(KNOWLEDGE_BASE_DIR.glob("**/*.md"))
    if not md_files:
        logging.warning(f"No markdown files (.md) found in '{KNOWLEDGE_BASE_DIR}'.")
        return []

    logging.info(f"Found {len(md_files)} document(s) to load.")

    all_documents: List[Document] = []
    for doc_path in md_files:
        try:
            loader = TextLoader(str(doc_path), encoding="utf-8")
            all_documents.extend(loader.load())
        except Exception as e:
            logging.error(f"Error loading document {doc_path}: {e}")

    if not all_documents:
        logging.error("Could not load any documents. Aborting.")
        return []

    # 2. Initialize a text splitter for chunking
    # chunk_size: The maximum number of characters in a chunk.
    # chunk_overlap: The number of characters to overlap between chunks to maintain context.
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)

    # 3. Split the loaded documents into chunks
    chunked_documents = text_splitter.split_documents(all_documents)

    return chunked_documents


if __name__ == "__main__":
    # This block allows the script to be run directly from the command line.
    # It configures basic logging and calls the main orchestration function.
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stdout,
    )
    asyncio.run(create_vector_store())