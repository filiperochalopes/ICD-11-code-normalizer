from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_SIMPLE_TABULATION_ZIP_URL = (
    "https://icdcdn.who.int/static/releasefiles/2024-01/"
    "SimpleTabulation-ICD-11-MMS-en.zip"
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = Field(default="icd11-code-normalizer", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    app_port: int = Field(default=8000, alias="APP_PORT")
    auth_token: str = Field(default="change-me", alias="AUTH_TOKEN")
    sqlite_path: str = Field(default="/data/app.db", alias="SQLITE_PATH")
    simple_tabulation_zip_url: str = Field(
        default=DEFAULT_SIMPLE_TABULATION_ZIP_URL,
        alias="SIMPLE_TABULATION_ZIP_URL",
    )
    openrouter_api_key: str = Field(default="", alias="OPENROUTER_API_KEY")
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        alias="OPENROUTER_BASE_URL",
    )
    openrouter_model: str = Field(default="openrouter/free", alias="OPENROUTER_MODEL")
    llm_timeout_seconds: int = Field(default=45, alias="LLM_TIMEOUT_SECONDS")
    prompt_version: str = Field(default="v1", alias="PROMPT_VERSION")
    ocl_base_url: str = Field(
        default="https://api.openconceptlab.org",
        alias="OCL_BASE_URL",
    )
    ocl_token: str = Field(default="", alias="OCL_TOKEN")
    ocl_lookup_source: str = Field(
        default="/orgs/OpenMRS-OCL-Squad/sources/ICD-11-WHO-Mapper/",
        alias="OCL_LOOKUP_SOURCE",
    )
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    code_normalizer_root_path: str = Field(
        default="",
        alias="ROOT_PATH",
    )

    @field_validator("code_normalizer_root_path", mode="before")
    @classmethod
    def normalize_code_normalizer_root_path(cls, value: str | None) -> str:
        """
        Normalize the reverse-proxy prefix used by the code-normalizer service.

        Parameters:
        - value: Raw environment value for ROOT_PATH.

        Returns:
        - str: Normalized prefix with leading slash and no trailing slash.

        Business Rules:
        - Empty or unset values disable root_path support.
        - Prefixes must start with a slash for FastAPI root_path compatibility.
        - A single slash is treated as no prefix because the service already lives at root internally.

        Examples:
        - "code-normalizer-api/" -> "/code-normalizer-api"
        - "" -> ""
        """
        candidate = (value or "").strip()
        if not candidate or candidate == "/":
            return ""
        if not candidate.startswith("/"):
            candidate = f"/{candidate}"
        return candidate.rstrip("/")

    @property
    def database_url(self) -> str:
        if self.sqlite_path.startswith("sqlite"):
            return self.sqlite_path
        if self.sqlite_path == ":memory:":
            return "sqlite+pysqlite:///:memory:"
        return f"sqlite+pysqlite:///{self.sqlite_path}"

    @staticmethod
    def mask_secret(value: str) -> str:
        if not value:
            return "<not-set>"
        if len(value) <= 8:
            return "*" * len(value)
        return f"{value[:4]}...{value[-4:]}"

    def public_summary(self) -> dict[str, str | int]:
        return {
            "app_name": self.app_name,
            "app_env": self.app_env,
            "app_port": self.app_port,
            "sqlite_path": self.sqlite_path,
            "simple_tabulation_zip_url": self.simple_tabulation_zip_url,
            "auth_token": self.mask_secret(self.auth_token),
            "openrouter_api_key": self.mask_secret(self.openrouter_api_key),
            "openrouter_base_url": self.openrouter_base_url,
            "openrouter_model": self.openrouter_model,
            "llm_timeout_seconds": self.llm_timeout_seconds,
            "prompt_version": self.prompt_version,
            "ocl_base_url": self.ocl_base_url,
            "ocl_token": self.mask_secret(self.ocl_token),
            "ocl_lookup_source": self.ocl_lookup_source,
            "log_level": self.log_level,
            "code_normalizer_root_path": self.code_normalizer_root_path,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
