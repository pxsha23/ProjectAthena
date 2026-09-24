"""Application settings, loaded from environment variables and server/.env."""

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

ProviderName = Literal["api", "local", "fake"]
AgentName = Literal["idea", "stack", "code", "summary", "eva", "chat"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- App ---
    app_env: Literal["development", "test", "production"] = "development"
    secret_key: str = Field(min_length=32)
    frontend_url: str = "http://localhost:5173"
    # Comma-separated in .env (NoDecode stops pydantic-settings from expecting JSON).
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]

    # --- Database ---
    database_url: str = "postgresql+asyncpg://athena:athena@localhost:5433/athena"
    database_echo: bool = False

    # --- Auth ---
    access_token_minutes: int = 15
    refresh_token_days: int = 7
    cookie_secure: bool = False
    cookie_domain: str | None = None

    # --- GitHub OAuth ---
    github_client_id: str | None = None
    github_client_secret: str | None = None
    github_redirect_uri: str = "http://localhost:5173/api/auth/github/callback"
    github_api_url: str = "https://api.github.com"
    github_oauth_url: str = "https://github.com/login/oauth"

    # --- LLM: Anthropic ("api") ---
    anthropic_api_key: str | None = None
    anthropic_model: str | None = None
    anthropic_max_tokens: int = 16000
    # Server-side refusal fallback (Anthropic API only). Disable if you route through Bedrock/Vertex.
    anthropic_refusal_fallback: bool = True

    # --- LLM: Ollama ("local") ---
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str | None = None
    # CPU-only machines are slow: a Code Agent run can take many minutes.
    ollama_timeout_seconds: float = 1800.0
    # Ollama's default context window is small and it silently drops what does not fit.
    ollama_num_ctx: int = 16384
    ollama_max_tokens: int = 8192
    # How long Ollama keeps the model in memory between calls.
    ollama_keep_alive: str = "30m"

    # --- Per-agent provider selection ("api" = Anthropic, "local" = Ollama, "fake" = canned test data) ---
    agent_idea_provider: ProviderName = "api"
    agent_stack_provider: ProviderName = "api"
    agent_code_provider: ProviderName = "api"
    agent_summary_provider: ProviderName = "api"
    agent_eva_provider: ProviderName = "api"
    agent_chat_provider: ProviderName = "api"

    # Optional per-agent model overrides. Empty means use ANTHROPIC_MODEL / OLLAMA_MODEL.
    agent_idea_model: str | None = None
    agent_stack_model: str | None = None
    agent_code_model: str | None = None
    agent_summary_model: str | None = None
    agent_eva_model: str | None = None
    agent_chat_model: str | None = None

    # How many times an agent may retry after returning output that fails schema validation.
    agent_max_retries: int = 2

    # --- Embeddings / code search ---
    embeddings_backend: Literal["sentence-transformers", "hash"] = "sentence-transformers"
    embeddings_model: str | None = None
    embedding_dim: int = 384

    @field_validator("database_url")
    @classmethod
    def use_async_driver(cls, value: str) -> str:
        # Hosts such as Render hand out plain postgres:// URLs; the app needs the asyncpg driver.
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                return "postgresql+asyncpg://" + value[len(prefix) :]
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_origins(cls, value: object) -> object:
        if isinstance(value, str) and not value.startswith("["):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    def provider_for(self, agent: AgentName) -> ProviderName:
        return getattr(self, f"agent_{agent}_provider")

    def model_override_for(self, agent: AgentName) -> str | None:
        return getattr(self, f"agent_{agent}_model") or None


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
