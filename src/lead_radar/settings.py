"""Application settings: environment variables plus YAML configuration.

Environment variables (via .env) hold secrets and machine-specific paths.
YAML files under config/ hold everything else — ICP criteria, scoring
weights, taxonomies — so they can be edited without touching code.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "config"


class Settings(BaseSettings):
    """Environment-sourced settings. See .env.example for the full list."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="", extra="ignore")

    anthropic_api_key: str | None = None
    vpai_api_key: str | None = None
    vibe_account_emails: str = ""
    lead_radar_db_path: str = "data/lead_radar.db"
    lead_radar_provider: str = "mock"

    @property
    def vibe_account_email_list(self) -> list[str]:
        return [e.strip() for e in self.vibe_account_emails.split(",") if e.strip()]

    @property
    def db_path(self) -> Path:
        path = Path(self.lead_radar_db_path)
        if not path.is_absolute():
            path = REPO_ROOT / path
        return path


class YamlConfig(BaseModel):
    """Thin, permissive wrapper around a loaded YAML config file.

    Kept as raw dict-backed access rather than a strict schema so that
    config files can grow new keys (new signals, new ICP dimensions)
    without requiring a code change in this loader. Consumers (hard gates,
    scoring engine) validate the specific keys they read.
    """

    data: dict[str, Any]

    def __getitem__(self, key: str) -> Any:
        return self.data[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)


def _load_yaml(name: str) -> YamlConfig:
    path = CONFIG_DIR / name
    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    return YamlConfig(data=raw)


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_icp_config() -> YamlConfig:
    return _load_yaml("icp.yaml")


@lru_cache
def get_scoring_config() -> YamlConfig:
    return _load_yaml("scoring.yaml")


@lru_cache
def get_signal_taxonomy() -> YamlConfig:
    return _load_yaml("signal_taxonomy.yaml")


@lru_cache
def get_title_taxonomy() -> YamlConfig:
    return _load_yaml("title_taxonomy.yaml")


@lru_cache
def get_exclusions_config() -> YamlConfig:
    return _load_yaml("exclusions.yaml")


@lru_cache
def get_providers_config() -> YamlConfig:
    return _load_yaml("providers.yaml")
