# tests/test_rag.py

import asyncio
from unittest.mock import AsyncMock

import pytest
import httpx
from langchain_core.documents import Document

# Import the private function we want to test
from app.core.rag import _load_and_split_documents, ApiServiceEmbeddings

@pytest.fixture
def temp_knowledge_base(tmp_path, monkeypatch):
    """
    Creates a temporary knowledge base directory with a sample markdown file.
    It then patches the KNOWLEDGE_BASE_DIR constant in the rag module to point
    to this temporary directory.
    """
    # Create a temporary directory for the knowledge base
    kb_dir = tmp_path / "knowledge_base"
    kb_dir.mkdir()

    # Create a sample markdown file
    sample_content = (
        "This is the first sentence. " * 50
        + "This is the second sentence, which will be in a separate chunk. " * 50
    )
    (kb_dir / "sample.md").write_text(sample_content, encoding="utf-8")

    # Patch the constant in the rag module
    monkeypatch.setattr("app.core.rag.KNOWLEDGE_BASE_DIR", kb_dir)
    return kb_dir


def test_load_and_split_documents(temp_knowledge_base):
    """
    Tests that _load_and_split_documents correctly loads a file,
    splits it into chunks, and returns a list of Document objects.
    """
    # Call the function to be tested
    chunked_documents = _load_and_split_documents()

    # Assertions
    assert isinstance(chunked_documents, list)
    assert len(chunked_documents) > 1  # Based on the content and splitter settings
    assert all(isinstance(doc, Document) for doc in chunked_documents)
    assert chunked_documents[0].page_content.startswith("This is the first sentence.")


@pytest.mark.asyncio
async def test_api_service_embeddings_success():
    """
    Tests the ApiServiceEmbeddings class for successful API calls.
    It mocks the httpx.AsyncClient to simulate a successful response.
    """
    # 1. Setup mock client and response
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_response = AsyncMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {"embeddings": [[0.1, 0.2], [0.3, 0.4]]}
    mock_client.post.return_value = mock_response

    # 2. Initialize the class with the mock client
    loop = asyncio.get_running_loop()
    embeddings_service = ApiServiceEmbeddings(
        api_url="http://fake-url/embed", async_client=mock_client, loop=loop
    )

    # 3. Test aembed_documents
    texts = ["hello", "world"]
    result = await embeddings_service.aembed_documents(texts)

    # 4. Assertions
    mock_client.post.assert_called_once_with("http://fake-url/embed", json={"texts": texts}, timeout=60.0)
    assert result == [[0.1, 0.2], [0.3, 0.4]]


@pytest.mark.asyncio
async def test_api_service_embeddings_http_error():
    """
    Tests that ApiServiceEmbeddings correctly raises an HTTPStatusError
    when the API returns an error status code.
    """
    # 1. Setup mock client to raise an error
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    error_response = httpx.Response(status_code=500, json={"detail": "Internal Server Error"})
    mock_client.post.side_effect = httpx.HTTPStatusError(
        "Server error", request=AsyncMock(), response=error_response
    )

    # 2. Initialize the class with the mock client
    loop = asyncio.get_running_loop()
    embeddings_service = ApiServiceEmbeddings(
        api_url="http://fake-url/embed", async_client=mock_client, loop=loop
    )

    # 3. Assert that the correct exception is raised
    with pytest.raises(httpx.HTTPStatusError):
        await embeddings_service.aembed_documents(["test text"])