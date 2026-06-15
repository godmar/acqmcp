from functools import cached_property
from pathlib import Path
from urllib.parse import urlparse

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    acq_api_key: str = Field(alias="ACQ_API_KEY")
    acq_base_url: str = Field(alias="ACQ_BASE_URL")
    acq_mcp_bearer_token: str = Field(alias="ACQ_MCP_BEARER_TOKEN")
    acq_mcp_url: str = Field(alias="ACQ_MCP_URL")

    acq_openapi_path: Path = Field(default=Path("acq.json"), alias="ACQ_OPENAPI_PATH")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")
    request_timeout_seconds: float = Field(default=30.0, alias="ACQ_REQUEST_TIMEOUT_SECONDS")

    @field_validator("acq_mcp_bearer_token")
    @classmethod
    def token_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("ACQ_MCP_BEARER_TOKEN must not be blank")
        return value

    @field_validator("acq_api_key")
    @classmethod
    def api_key_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("ACQ_API_KEY must not be blank")
        return value

    @field_validator("acq_base_url", "acq_mcp_url")
    @classmethod
    def normalize_url(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("URL values must not be blank")
        if "://" not in normalized:
            normalized = f"https://{normalized}"
        parsed = urlparse(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError(f"Invalid URL: {value}")
        return normalized

    @cached_property
    def base_url(self) -> str:
        return self.acq_base_url.rstrip("/")

    @cached_property
    def public_url(self) -> str:
        return self.acq_mcp_url.rstrip("/")

    @cached_property
    def public_path_prefix(self) -> str:
        parsed = urlparse(self.public_url)
        return parsed.path.rstrip("/")

    @cached_property
    def mcp_endpoint_url(self) -> str:
        return f"{self.public_url}/mcp"
