# BotGPT - RAG Chatbot

An asynchronous, event-driven chatbot capability of "Chatting with PDFs". Built with **FastAPI**, **LangChain**, **Celery**, **Redis**, and **PostgreSQL (pgvector)**.

## 🚀 Key Features

* **RAG Pipeline:** Asynchronous PDF ingestion using Celery workers.
* **Vector Search:** HNSW indexing via `pgvector` for O(log n) retrieval.
* **Real-Time:** Socket.IO integration for instant updates.
* **Cost Optimized:** Deduplication of embeddings (Hashing) and Sliding Window context.
* **Robust Parsing:** Uses `PyMuPDF` for handling complex PDF layouts.

## 🛠️ Tech Stack

* **Backend:** FastAPI, Python 3.11
* **Database:** PostgreSQL 16 + pgvector
* **Async Queue:** Celery + Redis
* **LLM Orchestration:** LangChain
* **Containerization:** Docker Compose

## 🏃‍♂️ Quick Start

1.  **Clone the repository**
    ```bash
    git clone <repo_url>
    cd bot-gpt
    ```

2.  **Configure Environment**
    Create a `.env` file (or rely on docker-compose defaults):
    ```ini
    OPENAI_API_KEY=sk-...  # Optional: If not provided, falls back to HuggingFace (CPU)
    ```

3.  **Run with Docker**
    ```bash
    docker compose up --build
    ```

4.  **Access the App**
    * **API Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
    * **Test Client:** Open `test_client.html` in your browser.

## 🧪 Testing the RAG Flow

1.  Open `test_client.html`.
2.  Create a **New Chat**.
3.  Upload a PDF (Resume, Manual, etc.).
4.  Wait for the alert: *"PDF Processed!"*.
5.  Ask a question specific to that PDF.

## 📂 Project Structure

```text
├── app/
│   ├── api/          # Endpoints (Chats, Documents)
│   ├── core/         # Config, DB, Celery Settings
│   ├── db/           # SQLAlchemy Models
│   ├── services/     # RAG Logic, Socket Manager
│   └── workers/      # Celery Tasks
├── docker-compose.yml
└── Dockerfile