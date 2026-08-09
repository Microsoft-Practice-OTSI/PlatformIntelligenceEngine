"""Environment configuration management for PIE using Pydantic Settings."""

import os
from enum import Enum
from pathlib import Path
from functools import lru_cache
from pydantic import Field, AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthMode(str, Enum):
    """Supported authentication strategies for Azure Entra ID."""
    INTERACTIVE = "interactive"
    DEVICE_CODE = "device_code"
    DEFAULT = "default"
    CLI = "cli"
    SERVICE_PRINCIPAL = "service_principal"
    MOCK = "mock"


class Settings(BaseSettings):
    """Centralized PIE configuration loaded from environment or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    # Authentication Strategy
    auth_mode: AuthMode = Field(
        default=AuthMode.DEFAULT,
        validation_alias=AliasChoices("PIE_AUTH_MODE", "AZURE_AUTH_MODE"),
        description="Azure Identity authentication method.",
    )

    # Entra ID Credentials
    tenant_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("AZURE_TENANT_ID", "TENANT_ID"),
        description="Microsoft Entra Tenant ID.",
    )
    client_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("AZURE_CLIENT_ID", "CLIENT_ID"),
        description="Azure Service Principal Client ID (App ID).",
    )
    client_secret: str | None = Field(
        default=None,
        validation_alias=AliasChoices("AZURE_CLIENT_SECRET", "CLIENT_SECRET"),
        description="Azure Service Principal Secret.",
    )

    # Target Scope (Optional)
    subscription_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("AZURE_SUBSCRIPTION_ID", "SUBSCRIPTION_ID"),
        description="Default Azure Subscription ID to target.",
    )
    resource_group: str | None = Field(
        default=None,
        validation_alias=AliasChoices("AZURE_RESOURCE_GROUP", "RESOURCE_GROUP"),
        description="Default Azure Resource Group to target.",
    )
    factory_name: str | None = Field(
        default=None,
        validation_alias=AliasChoices("AZURE_FACTORY_NAME", "FACTORY_NAME"),
        description="Default Azure Data Factory name.",
    )

    # AI Services (Spikes 4 & 5)
    ai_foundry_endpoint: str | None = Field(
        default=None,
        validation_alias=AliasChoices("AZURE_AI_FOUNDRY_ENDPOINT", "AI_FOUNDRY_ENDPOINT"),
    )
    ai_foundry_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("AZURE_AI_FOUNDRY_KEY", "AI_FOUNDRY_KEY"),
    )
    ai_foundry_model: str = Field(
        default="gpt-4o-mini",
        validation_alias=AliasChoices("AZURE_AI_FOUNDRY_MODEL", "AI_FOUNDRY_MODEL"),
    )
    ai_search_endpoint: str | None = Field(
        default=None,
        validation_alias=AliasChoices("AZURE_AI_SEARCH_ENDPOINT", "AI_SEARCH_ENDPOINT"),
    )
    ai_search_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("AZURE_AI_SEARCH_KEY", "AI_SEARCH_KEY"),
    )
    ai_search_index_name: str = Field(
        default="pie-adf-metadata-index",
        validation_alias=AliasChoices("AZURE_AI_SEARCH_INDEX_NAME", "AI_SEARCH_INDEX_NAME"),
    )

    # Runtime & Paths
    log_level: str = Field(
        default="INFO",
        validation_alias=AliasChoices("PIE_LOG_LEVEL", "LOG_LEVEL"),
    )
    output_dir: Path = Field(
        default=Path("output"),
        validation_alias=AliasChoices("PIE_OUTPUT_DIR", "OUTPUT_DIR"),
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings singleton."""
    return Settings()
