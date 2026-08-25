"""
Configuration module for the Duffel API Python client.
"""

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Optional


@dataclass
class DuffelConfig:
    """Configuration options for Duffel API client."""
    api_token: str = ""
    base_url: str = "https://api.duffel.com"
    api_version: str = "v2"
    timeout: float = 130.0
    debug: bool = False
    enable_cache: bool = True
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None
    cache_ttl_seconds: int = 3600
    max_cached_offers: int = 40
    max_non_stop_offers: int = 10
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.6-flash"
    gemini_enabled: bool = True
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"
    openai_enabled: bool = True
    llm_provider: str = "openai"
    max_retries: int = 3
    retry_backoff_factor: float = 0.5
    retry_backoff_max: float = 10.0
    retry_status_codes: Optional[list[int]] = None
    config_file: str = "config.json"

    def __post_init__(self):
        if self.retry_status_codes is None:
            self.retry_status_codes = [500, 502, 503, 504, 429]
        # 1. Load from config.json if present
        if Path(self.config_file).is_file():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    cfg_data = json.load(f)
                    if not self.api_token:
                        self.api_token = cfg_data.get("duffel_api_token") or cfg_data.get("api_token") or ""
                    if "base_url" in cfg_data and cfg_data["base_url"]:
                        self.base_url = cfg_data["base_url"]
                    if "api_version" in cfg_data and cfg_data["api_version"]:
                        self.api_version = cfg_data["api_version"]
                    if "timeout" in cfg_data and cfg_data["timeout"]:
                        self.timeout = float(cfg_data["timeout"])
                    if "debug" in cfg_data:
                        self.debug = bool(cfg_data["debug"])
                    if "enable_cache" in cfg_data:
                        self.enable_cache = bool(cfg_data["enable_cache"])
                    if "redis_host" in cfg_data and cfg_data["redis_host"]:
                        self.redis_host = str(cfg_data["redis_host"])
                    if "redis_port" in cfg_data:
                        self.redis_port = int(cfg_data["redis_port"])
                    if "redis_db" in cfg_data:
                        self.redis_db = int(cfg_data["redis_db"])
                    if "redis_password" in cfg_data:
                        self.redis_password = cfg_data["redis_password"]
                    if "cache_ttl_seconds" in cfg_data:
                        self.cache_ttl_seconds = int(cfg_data["cache_ttl_seconds"])
                    if "max_cached_offers" in cfg_data:
                        self.max_cached_offers = int(cfg_data["max_cached_offers"])
                    if "max_non_stop_offers" in cfg_data:
                        self.max_non_stop_offers = int(cfg_data["max_non_stop_offers"])
                    if "gemini_api_key" in cfg_data:
                        self.gemini_api_key = str(cfg_data["gemini_api_key"] or "")
                    if "gemini_model" in cfg_data and cfg_data["gemini_model"]:
                        self.gemini_model = str(cfg_data["gemini_model"])
                    if "gemini_enabled" in cfg_data:
                        self.gemini_enabled = bool(cfg_data["gemini_enabled"])
                    if "openai_api_key" in cfg_data:
                        self.openai_api_key = str(cfg_data["openai_api_key"] or "")
                    if "openai_model" in cfg_data and cfg_data["openai_model"]:
                        self.openai_model = str(cfg_data["openai_model"])
                    if "openai_enabled" in cfg_data:
                        self.openai_enabled = bool(cfg_data["openai_enabled"])
                    if "llm_provider" in cfg_data and cfg_data["llm_provider"]:
                        self.llm_provider = str(cfg_data["llm_provider"]).lower()
                    if "max_retries" in cfg_data and cfg_data["max_retries"] is not None:
                        self.max_retries = int(cfg_data["max_retries"])
                    if "retry_backoff_factor" in cfg_data and cfg_data["retry_backoff_factor"] is not None:
                        self.retry_backoff_factor = float(cfg_data["retry_backoff_factor"])
                    if "retry_backoff_max" in cfg_data and cfg_data["retry_backoff_max"] is not None:
                        self.retry_backoff_max = float(cfg_data["retry_backoff_max"])
                    if "retry_status_codes" in cfg_data and isinstance(cfg_data["retry_status_codes"], list):
                        self.retry_status_codes = [int(c) for c in cfg_data["retry_status_codes"]]
            except Exception:
                pass

        # 2. Fall back to environment variable if token is still empty
        if not self.api_token:
            self.api_token = os.environ.get("DUFFEL_API_TOKEN", "")
        if not self.gemini_api_key:
            self.gemini_api_key = os.environ.get("GEMINI_API_KEY", "")
        if os.environ.get("GEMINI_MODEL"):
            self.gemini_model = os.environ["GEMINI_MODEL"]
        if not self.openai_api_key:
            self.openai_api_key = os.environ.get("OPENAI_API_KEY", "")
        if os.environ.get("OPENAI_MODEL"):
            self.openai_model = os.environ["OPENAI_MODEL"]
        if os.environ.get("LLM_PROVIDER"):
            self.llm_provider = os.environ["LLM_PROVIDER"].lower()
        if os.environ.get("DUFFEL_MAX_RETRIES"):
            self.max_retries = int(os.environ["DUFFEL_MAX_RETRIES"])

    @property
    def headers(self) -> dict[str, str]:
        """Generate standard HTTP headers required by Duffel REST API."""
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Duffel-Version": self.api_version,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "DuffelPythonSDK/1.0.0",
        }
