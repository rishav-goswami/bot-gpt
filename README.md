# BotGPT - RAG Chatbot

An asynchronous, event-driven chatbot with "Chat with PDFs" capability. Built with **FastAPI**, **LangChain**, **LangGraph**, **Celery**, **Redis**, and **PostgreSQL (pgvector)**.

## 🚀 Key Features

* **RAG Pipeline:** Asynchronous PDF ingestion using Celery workers
* **Vector Search:** HNSW indexing via `pgvector` for efficient similarity search
* **Real-Time Updates:** Socket.IO integration for instant message delivery
* **Cost Optimized:** Deduplication of embeddings (file hashing) and sliding window context
* **Robust Parsing:** Uses `PyMuPDF` for handling complex PDF layouts
* **LLM Orchestration:** LangGraph workflow for intelligent routing between RAG and general chat
* **Multiple LLM Support:** OpenAI, Google Gemini, Groq, and Ollama

## 🛠️ Tech Stack

* **Backend:** FastAPI, Python 3.11+
* **Database:** PostgreSQL 16 + pgvector extension
* **Async Queue:** Celery + Redis
* **LLM Orchestration:** LangChain + LangGraph
* **Real-Time:** Socket.IO with Redis adapter
* **Containerization:** Docker Compose
* **Testing:** pytest, pytest-asyncio, httpx

## 📋 Prerequisites

* Docker and Docker Compose
* (Optional) LLM API keys (OpenAI, Groq, Google, etc.)

## 🏃‍♂️ Quick Start

### 1. Clone the Repository
```bash
git clone <repo_url>
cd bot-gpt
```

### 2. Configure Environment Variables

Create a `.env` file in the `backend/` directory (optional - defaults are provided):

```ini
# Database
DATABASE_URL=postgresql://app_user:app_password@db:5432/botgpt_db

# LLM Provider (options: openai, google, groq, ollama)
LLM_PROVIDER=groq

# API Keys (at least one required based on LLM_PROVIDER)
OPENAI_API_KEY=sk-...
GROQ_API_KEY=gsk_...
GOOGLE_API_KEY=...

# Embeddings (defaults to OpenAI if OPENAI_API_KEY is set, else HuggingFace)
OPENAI_API_KEY=sk-...  # For embeddings
EMBEDDING_MODEL=text-embedding-3-small

# Redis
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0

# CORS Origins (comma-separated)
BACKEND_CORS_ORIGINS=http://localhost:3000,http://localhost:8000
```

### 3. Start the Application

Using Docker Compose:
```bash
docker compose up --build
```

Or using Makefile:
```bash
make up
```

### 4. Access the Application

* **API Documentation:** [http://localhost:8000/docs](http://localhost:8000/docs)
* **ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)
* **Health Check:** [http://localhost:8000/health](http://localhost:8000/health)
* **Test Client:** Open `test.html` in your browser

## 📡 API Endpoints

### Health & Status

* `GET /` - Root endpoint with API information
* `GET /health/live` - Liveness probe (Kubernetes-style)
* `GET /health` - Full health check (includes database connectivity)

### Conversations

* `POST /api/v1/conversations/` - Create a new conversation
* `GET /api/v1/conversations/` - List all conversations (with pagination)
* `GET /api/v1/conversations/{chat_id}` - Get conversation details
* `POST /api/v1/conversations/{chat_id}/messages` - Send a message
* `DELETE /api/v1/conversations/{chat_id}` - Delete a conversation

### Documents

* `POST /api/v1/documents/` - Upload a PDF document
* `GET /api/v1/documents/{conversation_id}` - List documents for a conversation

### WebSocket (Socket.IO)

* Connect to `/socket.io` for real-time message updates
* Events:
  - `connect` - Connection established
  - `join_conversation` - Join a conversation room
  - `new_message` - Receive new messages
  - `doc_processed` - Document processing complete

## 🧪 Testing

### Running Tests

The project includes a comprehensive test suite with 20+ tests covering all API endpoints, error handling, and edge cases.

**Option 1: Using Docker (Recommended)**
```bash
docker exec botgpt_api poetry run pytest app/tests/test_api.py -v
```

**Option 2: Inside Container Shell**
```bash
# Enter the container
docker exec -it botgpt_api /bin/bash

# Run tests
poetry run pytest app/tests/test_api.py -v

# Run specific test
poetry run pytest app/tests/test_api.py::test_create_conversation -v

# Run with coverage (if installed)
poetry run pytest app/tests/test_api.py --cov=app --cov-report=html
```

### Test Coverage

The test suite includes:
* ✅ Health endpoint tests
* ✅ Conversation CRUD operations
* ✅ Message sending and receiving
* ✅ Document upload and validation
* ✅ Error handling (404, 400, validation errors)
* ✅ Pagination
* ✅ Edge cases

All external dependencies (LLM, SocketIO, Celery) are properly mocked to ensure fast and reliable tests.

## 🧪 Testing the RAG Flow (Manual)

1. Open `test.html` in your browser
2. Create a **New Chat** by sending your first message
3. Upload a PDF document (Resume, Manual, etc.)
4. Wait for the Socket.IO event: *"PDF Processed!"*
5. Ask questions specific to that PDF
6. The system will automatically use RAG when documents are attached

## 🏗️ Architecture

### Workflow

1. **User sends message** → Saved to database
2. **LangGraph workflow**:
   - Checks if conversation has documents
   - If yes: Retrieves relevant chunks using vector search
   - Generates response using RAG context
   - If no: Generates general conversation response
3. **Response saved** → Emitted via Socket.IO

### Document Processing

1. **Upload** → PDF saved to disk
2. **Celery task triggered** → Background processing
3. **PDF parsed** → Text extracted using PyMuPDF
4. **Chunking** → Recursive text splitter (1000 chars, 200 overlap)
5. **Embedding** → Generated using OpenAI or HuggingFace
6. **Storage** → Vectors stored in PostgreSQL with pgvector
7. **Deduplication** → File hash checking prevents reprocessing

## 📂 Project Structure

```
bot-gpt/
├── backend/
│   ├── app/
│   │   ├── api/              # API endpoints
│   │   │   ├── v1/
│   │   │   │   └── endpoints/
│   │   │   │       ├── chats.py      # Conversation endpoints
│   │   │   │       └── documents.py  # Document endpoints
│   │   ├── core/             # Core configuration
│   │   │   ├── config.py      # Settings management
│   │   │   ├── database.py   # Database connection
│   │   │   └── celery_app.py # Celery configuration
│   │   ├── crud/              # Database operations
│   │   │   ├── chat.py
│   │   │   └── document.py
│   │   ├── db/                # Database models
│   │   │   ├── models.py      # SQLAlchemy models
│   │   │   └── base.py        # Base classes
│   │   ├── services/          # Business logic
│   │   │   ├── rag_service.py      # RAG processing
│   │   │   ├── llm_graph.py        # LangGraph workflow
│   │   │   ├── socketio_manager.py # Real-time updates
│   │   │   └── prompts.py          # Prompt management
│   │   ├── workers/           # Celery tasks
│   │   │   └── tasks.py        # Background jobs
│   │   ├── schemas/           # Pydantic models
│   │   ├── middlewares/       # Custom middlewares
│   │   ├── tests/             # Test suite
│   │   │   ├── test_api.py    # API tests
│   │   │   └── conftest.py    # Test configuration
│   │   ├── main.py            # FastAPI application
│   │   └── llm_client.py      # LLM client factory
│   ├── Dockerfile
│   ├── pyproject.toml         # Poetry dependencies
│   └── uploads/               # Uploaded PDFs
├── docker-compose.yml
├── nginx/
│   └── nginx.conf
├── Makefile
└── README.md
```

## 🛠️ Development

### Makefile Commands

```bash
make up      # Start all services
make down    # Stop all services
make logs    # View logs (backend + worker)
make clean   # Stop services and remove volumes
make shell   # Open shell in API container
```

### Adding New Features

1. **New API Endpoint:**
   - Add route in `app/api/v1/endpoints/`
   - Add schema in `app/schemas/`
   - Add CRUD operations in `app/crud/`
   - Add tests in `app/tests/test_api.py`

2. **New Service:**
   - Create file in `app/services/`
   - Import and use in endpoints

3. **New Model:**
   - Add model in `app/db/models.py`
   - Create migration (if using Alembic)
   - Add CRUD operations

### Code Style

* Follow PEP 8
* Use type hints
* Async/await for I/O operations
* Proper error handling with HTTPException

## 🔧 Configuration

### LLM Providers

The system supports multiple LLM providers. Set `LLM_PROVIDER` in environment:

- **openai**: Uses GPT models (requires `OPENAI_API_KEY`)
- **google**: Uses Gemini (requires `GOOGLE_API_KEY`)
- **groq**: Uses Llama models (requires `GROQ_API_KEY`) - Fast and free tier available
- **ollama**: Local models (requires `OLLAMA_BASE_URL`)

### Embeddings

- **OpenAI**: If `OPENAI_API_KEY` is set, uses `text-embedding-3-small` (1536 dims)
- **HuggingFace**: Falls back to `sentence-transformers/all-MiniLM-L6-v2` (384 dims) if no OpenAI key

## 🐛 Troubleshooting

### Database Connection Issues

```bash
# Check if database is running
docker ps | grep botgpt_db

# Check database logs
docker logs botgpt_db

# Verify connection string in docker-compose.yml
```

### Celery Worker Not Processing

```bash
# Check worker logs
docker logs botgpt_worker

# Verify Redis connection
docker exec botgpt_redis redis-cli ping
```

### Tests Failing

```bash
# Ensure database is running
docker compose up -d db

# Run tests with verbose output
docker exec botgpt_api poetry run pytest app/tests/test_api.py -v -s
```

## 📝 License

[Add your license here]

## 👥 Contributors

* Rishav Anand - [GitHub](https://github.com/rishav-goswami)

## 🙏 Acknowledgments

* FastAPI for the excellent async framework
* LangChain for LLM orchestration
* pgvector for PostgreSQL vector extension
* All open-source contributors
