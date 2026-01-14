"""
Comprehensive API tests with proper mocking for LLM, SocketIO, and Celery.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from langchain_core.messages import AIMessage


@pytest.mark.asyncio
async def test_health_live(client):
    """Test liveness health check endpoint."""
    response = await client.get("/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "bot-gpt-backend"


@pytest.mark.asyncio
async def test_health_check(client):
    """Test full health check endpoint."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "database" in data
    assert "latency_ms" in data


@pytest.mark.asyncio
async def test_root_endpoint(client):
    """Test root endpoint."""
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "docs" in data
    assert "health" in data


# --- Conversation Tests ---


@pytest.mark.asyncio
@patch("app.api.v1.endpoints.chats.app_graph.ainvoke")
@patch("app.api.v1.endpoints.chats.sio.emit_to_room")
async def test_create_conversation(mock_sio, mock_graph, client):
    """Test creating a new conversation with mocked LLM."""
    # Mock LLM graph response
    mock_ai_message = AIMessage(content="Hello! How can I help you today?")
    mock_graph.return_value = {
        "messages": [mock_ai_message],
        "context": "",
        "has_documents": False,
    }
    mock_sio.return_value = None

    payload = {"first_message": "Hello BotGPT!"}

    response = await client.post("/api/v1/conversations/", json=payload)

    assert response.status_code == 201, f"Error: {response.text}"
    data = response.json()
    assert "id" in data
    assert "messages" in data
    assert len(data["messages"]) >= 1
    assert data["messages"][0]["content"] == "Hello BotGPT!"
    assert data["messages"][0]["role"] == "user"
    assert "title" in data
    assert "created_at" in data

    # Verify LLM was called
    mock_graph.assert_called_once()
    # Verify SocketIO was called (at least once for user message, once for AI)
    assert mock_sio.call_count >= 1


@pytest.mark.asyncio
@patch("app.api.v1.endpoints.chats.app_graph.ainvoke")
@patch("app.api.v1.endpoints.chats.sio.emit_to_room")
async def test_create_conversation_with_doc_ids(mock_sio, mock_graph, client):
    """Test creating conversation with document IDs."""
    mock_ai_message = AIMessage(content="I can help you with your documents!")
    mock_graph.return_value = {
        "messages": [mock_ai_message],
        "context": "",
        "has_documents": True,
    }
    mock_sio.return_value = None

    doc_id = str(uuid4())
    payload = {"first_message": "What's in my document?", "doc_ids": [doc_id]}

    response = await client.post("/api/v1/conversations/", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert "id" in data


@pytest.mark.asyncio
async def test_create_conversation_validation_error(client):
    """Test conversation creation with invalid payload."""
    # Empty message
    response = await client.post("/api/v1/conversations/", json={"first_message": ""})
    assert response.status_code == 422

    # Missing field
    response = await client.post("/api/v1/conversations/", json={})
    assert response.status_code == 422


@pytest.mark.asyncio
@patch("app.api.v1.endpoints.chats.app_graph.ainvoke")
@patch("app.api.v1.endpoints.chats.sio.emit_to_room")
async def test_list_conversations(mock_sio, mock_graph, client):
    """Test listing conversations."""
    # Create a conversation first
    mock_ai_message = AIMessage(content="Test response")
    mock_graph.return_value = {
        "messages": [mock_ai_message],
        "context": "",
        "has_documents": False,
    }
    mock_sio.return_value = None

    await client.post("/api/v1/conversations/", json={"first_message": "Test 1"})
    await client.post("/api/v1/conversations/", json={"first_message": "Test 2"})

    # List conversations
    response = await client.get("/api/v1/conversations/")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 2

    # Check structure
    if len(data) > 0:
        conv = data[0]
        assert "id" in conv
        assert "title" in conv
        assert "created_at" in conv
        assert "updated_at" in conv


@pytest.mark.asyncio
@patch("app.api.v1.endpoints.chats.app_graph.ainvoke")
@patch("app.api.v1.endpoints.chats.sio.emit_to_room")
async def test_list_conversations_pagination(mock_sio, mock_graph, client):
    """Test conversation list pagination."""
    mock_ai_message = AIMessage(content="Test")
    mock_graph.return_value = {
        "messages": [mock_ai_message],
        "context": "",
        "has_documents": False,
    }
    mock_sio.return_value = None

    # Create multiple conversations
    for i in range(5):
        await client.post(
            "/api/v1/conversations/", json={"first_message": f"Message {i}"}
        )

    # Test pagination
    response = await client.get("/api/v1/conversations/?skip=0&limit=2")
    assert response.status_code == 200
    data = response.json()
    assert len(data) <= 2

    response = await client.get("/api/v1/conversations/?skip=2&limit=2")
    assert response.status_code == 200


@pytest.mark.asyncio
@patch("app.api.v1.endpoints.chats.app_graph.ainvoke")
@patch("app.api.v1.endpoints.chats.sio.emit_to_room")
async def test_get_conversation(mock_sio, mock_graph, client):
    """Test getting a specific conversation."""
    mock_ai_message = AIMessage(content="Test response")
    mock_graph.return_value = {
        "messages": [mock_ai_message],
        "context": "",
        "has_documents": False,
    }
    mock_sio.return_value = None

    # Create conversation
    create_res = await client.post(
        "/api/v1/conversations/", json={"first_message": "Get me"}
    )
    chat_id = create_res.json()["id"]

    # Get conversation
    response = await client.get(f"/api/v1/conversations/{chat_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == chat_id
    assert "messages" in data
    assert "documents" in data
    assert len(data["messages"]) >= 1


@pytest.mark.asyncio
async def test_get_conversation_not_found(client):
    """Test getting non-existent conversation."""
    fake_id = str(uuid4())
    response = await client.get(f"/api/v1/conversations/{fake_id}")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
@patch("app.api.v1.endpoints.chats.app_graph.ainvoke")
@patch("app.api.v1.endpoints.chats.sio.emit_to_room")
async def test_send_message(mock_sio, mock_graph, client):
    """Test sending a message to a conversation."""
    mock_ai_message = AIMessage(content="I'm here to help!")
    mock_graph.return_value = {
        "messages": [mock_ai_message],
        "context": "",
        "has_documents": False,
    }
    mock_sio.return_value = None

    # Create conversation
    start_res = await client.post(
        "/api/v1/conversations/", json={"first_message": "Init"}
    )
    chat_id = start_res.json()["id"]

    # Send message
    payload = {"content": "Who are you?", "role": "user"}
    response = await client.post(
        f"/api/v1/conversations/{chat_id}/messages", json=payload
    )

    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "assistant"
    assert "content" in data
    assert data["conversation_id"] == chat_id
    assert "id" in data
    assert "created_at" in data

    # Verify LLM was called
    mock_graph.assert_called()


@pytest.mark.asyncio
@patch("app.api.v1.endpoints.chats.app_graph.ainvoke")
@patch("app.api.v1.endpoints.chats.sio.emit_to_room")
async def test_send_message_conversation_not_found(mock_sio, mock_graph, client):
    """Test sending message to non-existent conversation."""
    fake_id = str(uuid4())
    payload = {"content": "Hello", "role": "user"}
    response = await client.post(
        f"/api/v1/conversations/{fake_id}/messages", json=payload
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_send_message_validation_error(client):
    """Test sending message with invalid payload."""
    fake_id = str(uuid4())
    # Empty content
    response = await client.post(
        f"/api/v1/conversations/{fake_id}/messages", json={"content": ""}
    )
    assert response.status_code == 422

    # Missing content
    response = await client.post(
        f"/api/v1/conversations/{fake_id}/messages", json={}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
@patch("app.api.v1.endpoints.chats.app_graph.ainvoke")
@patch("app.api.v1.endpoints.chats.sio.emit_to_room")
async def test_delete_conversation(mock_sio, mock_graph, client):
    """Test deleting a conversation."""
    mock_ai_message = AIMessage(content="Test")
    mock_graph.return_value = {
        "messages": [mock_ai_message],
        "context": "",
        "has_documents": False,
    }
    mock_sio.return_value = None

    # Create conversation
    start_res = await client.post(
        "/api/v1/conversations/", json={"first_message": "Delete me"}
    )
    chat_id = start_res.json()["id"]

    # Delete conversation
    response = await client.delete(f"/api/v1/conversations/{chat_id}")
    assert response.status_code == 204

    # Verify it's gone
    get_res = await client.get(f"/api/v1/conversations/{chat_id}")
    assert get_res.status_code == 404


@pytest.mark.asyncio
async def test_delete_conversation_not_found(client):
    """Test deleting non-existent conversation."""
    fake_id = str(uuid4())
    response = await client.delete(f"/api/v1/conversations/{fake_id}")
    assert response.status_code == 404


# --- Document Tests ---


@pytest.mark.asyncio
@patch("app.api.v1.endpoints.documents.ingest_pdf_task.delay")
@patch("app.api.v1.endpoints.chats.app_graph.ainvoke")
@patch("app.api.v1.endpoints.chats.sio.emit_to_room")
async def test_upload_document(mock_sio, mock_graph, mock_celery, client):
    """Test uploading a document."""
    mock_ai_message = AIMessage(content="Test")
    mock_graph.return_value = {
        "messages": [mock_ai_message],
        "context": "",
        "has_documents": False,
    }
    mock_sio.return_value = None
    mock_celery.return_value = None

    # Create conversation first
    create_res = await client.post(
        "/api/v1/conversations/", json={"first_message": "Upload test"}
    )
    chat_id = create_res.json()["id"]

    # Create a mock PDF file
    files = {"file": ("test.pdf", b"%PDF-1.4 fake pdf content", "application/pdf")}
    data = {"conversation_id": chat_id}

    response = await client.post(
        "/api/v1/documents/", files=files, data=data
    )

    assert response.status_code == 201
    response_data = response.json()
    assert "id" in response_data
    assert response_data["filename"] == "test.pdf"
    assert response_data["conversation_id"] == chat_id
    assert "file_path" in response_data
    assert "created_at" in response_data

    # Verify Celery task was triggered
    mock_celery.assert_called_once()


@pytest.mark.asyncio
@patch("app.api.v1.endpoints.chats.app_graph.ainvoke")
@patch("app.api.v1.endpoints.chats.sio.emit_to_room")
async def test_upload_document_invalid_file_type(mock_sio, mock_graph, client):
    """Test uploading non-PDF file."""
    mock_ai_message = AIMessage(content="Test")
    mock_graph.return_value = {
        "messages": [mock_ai_message],
        "context": "",
        "has_documents": False,
    }
    mock_sio.return_value = None

    create_res = await client.post(
        "/api/v1/conversations/", json={"first_message": "Test"}
    )
    chat_id = create_res.json()["id"]

    # Try to upload non-PDF
    files = {"file": ("test.txt", b"text content", "text/plain")}
    data = {"conversation_id": chat_id}

    response = await client.post("/api/v1/documents/", files=files, data=data)
    assert response.status_code == 400
    assert "pdf" in response.json()["detail"].lower()


@pytest.mark.asyncio
@patch("app.api.v1.endpoints.chats.app_graph.ainvoke")
@patch("app.api.v1.endpoints.chats.sio.emit_to_room")
async def test_list_documents(mock_sio, mock_graph, client):
    """Test listing documents for a conversation."""
    mock_ai_message = AIMessage(content="Test")
    mock_graph.return_value = {
        "messages": [mock_ai_message],
        "context": "",
        "has_documents": False,
    }
    mock_sio.return_value = None

    # Create conversation
    create_res = await client.post(
        "/api/v1/conversations/", json={"first_message": "List docs"}
    )
    chat_id = create_res.json()["id"]

    # List documents (should be empty initially)
    response = await client.get(f"/api/v1/documents/{chat_id}")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
@patch("app.api.v1.endpoints.documents.ingest_pdf_task.delay")
@patch("app.api.v1.endpoints.chats.app_graph.ainvoke")
@patch("app.api.v1.endpoints.chats.sio.emit_to_room")
async def test_list_documents_after_upload(mock_sio, mock_graph, mock_celery, client):
    """Test listing documents after upload."""
    mock_ai_message = AIMessage(content="Test")
    mock_graph.return_value = {
        "messages": [mock_ai_message],
        "context": "",
        "has_documents": False,
    }
    mock_sio.return_value = None
    mock_celery.return_value = None

    # Create conversation
    create_res = await client.post(
        "/api/v1/conversations/", json={"first_message": "Upload and list"}
    )
    chat_id = create_res.json()["id"]

    # Upload document
    files = {"file": ("test.pdf", b"%PDF-1.4 fake pdf", "application/pdf")}
    data = {"conversation_id": chat_id}
    await client.post("/api/v1/documents/", files=files, data=data)

    # List documents
    response = await client.get(f"/api/v1/documents/{chat_id}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    if len(data) > 0:
        doc = data[0]
        assert "id" in doc
        assert "filename" in doc
        assert doc["conversation_id"] == chat_id


@pytest.mark.asyncio
async def test_list_documents_invalid_conversation_id(client):
    """Test listing documents for non-existent conversation."""
    fake_id = str(uuid4())
    response = await client.get(f"/api/v1/documents/{fake_id}")
    # Should return empty list, not error
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 0
