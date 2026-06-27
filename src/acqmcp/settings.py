from functools import cached_property
from pathlib import Path
from urllib.parse import urlparse

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    acq_api_key: str = Field(alias="ACQ_API_KEY")
    bibs_api_key: str = Field(alias="BIBS_API_KEY")
    api_base_url: str = Field(alias="API_BASE_URL")
    mcp_bearer_token: str = Field(alias="MCP_BEARER_TOKEN")
    mcp_url: str = Field(alias="MCP_URL")

    acq_openapi_path: Path = Field(default=Path("acq.json"), alias="ACQ_OPENAPI_PATH")
    bibs_openapi_path: Path = Field(default=Path("bibs.json"), alias="BIBS_OPENAPI_PATH")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")
    request_timeout_seconds: float = Field(default=30.0, alias="REQUEST_TIMEOUT_SECONDS")

    @field_validator("mcp_bearer_token")
    @classmethod
    def token_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("MCP_BEARER_TOKEN must not be blank")
        return value

    @field_validator("acq_api_key", "bibs_api_key")
    @classmethod
    def api_key_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("API key values must not be blank")
        return value

    @field_validator("api_base_url", "mcp_url")
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
        return self.api_base_url.rstrip("/")

    @cached_property
    def public_url(self) -> str:
        return self.mcp_url.rstrip("/")

    @cached_property
    def public_path_prefix(self) -> str:
        parsed = urlparse(self.public_url)
        return parsed.path.rstrip("/")

    @cached_property
    def mcp_endpoint_url(self) -> str:
        return f"{self.public_url}/mcp"
