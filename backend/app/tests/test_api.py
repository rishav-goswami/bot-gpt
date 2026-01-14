import pytest


@pytest.mark.asyncio
async def test_create_conversation(client):
    # This payload matches your ChatCreate schema
    payload = {"first_message": "Hello BotGPT!"}

    response = await client.post("/api/v1/conversations/", json=payload)

    # If this fails, check app/schemas/chat.py for 'doc_ids' field
    assert response.status_code == 201, f"Error: {response.text}"
    data = response.json()
    assert "id" in data
    assert data["messages"][0]["content"] == "Hello BotGPT!"


@pytest.mark.asyncio
async def test_send_message(client):
    # 1. Create chat
    start_res = await client.post(
        "/api/v1/conversations/", json={"first_message": "Init"}
    )
    chat_id = start_res.json()["id"]

    # 2. Send message
    payload = {"content": "Who are you?", "role": "user"}
    response = await client.post(
        f"/api/v1/conversations/{chat_id}/messages", json=payload
    )

    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "assistant"


@pytest.mark.asyncio
async def test_delete_conversation(client):
    # 1. Create
    start_res = await client.post(
        "/api/v1/conversations/", json={"first_message": "Delete me"}
    )
    chat_id = start_res.json()["id"]

    # 2. Delete
    response = await client.delete(f"/api/v1/conversations/{chat_id}")
    assert response.status_code == 204

    # 3. Verify it's gone
    get_res = await client.get(f"/api/v1/conversations/{chat_id}")
    assert get_res.status_code == 404
