
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_ollama import ChatOllama
from app.core.config import settings


class LLMClient:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """Initializes the LLM client based on the provider in settings."""
        provider = settings.LLM_PROVIDER.lower()

        if provider == "openai":
            self.llm = ChatOpenAI(
                temperature=0.7,
                model_name="gpt-4.1",
                openai_api_key=settings.OPENAI_API_KEY,
            )
            print("Initialized OpenAI LLM Client.")
        elif provider == "google":
            self.llm = ChatGoogleGenerativeAI(
                model="gemini-pro", google_api_key=settings.GOOGLE_API_KEY
            )
            print("Initialized Google Gemini LLM Client.")
        elif provider == "groq":
            self.llm = ChatGroq(
                temperature=0.7,
                groq_api_key=settings.GROQ_API_KEY,
                model_name="llama-3.3-70b-versatile",
            )
            print("Initialized Groq LLM Client.")
        elif provider == "ollama":
            self.llm = ChatOllama(
                model=settings.OLLAMA_MODEL,
                temperature=0,
                base_url=settings.OLLAMA_BASE_URL,
            )
            print(f"Initialized Ollama LLM Client with model {settings.OLLAMA_MODEL}.")
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")

    def get_llm(self):
        return self.llm


# single, global instance of the client
llm_client = LLMClient()
