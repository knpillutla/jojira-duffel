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
    timeout: float = 5.0
    force_instant_booking: bool = False
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
    service_bus_enabled: bool = True
    service_bus_connection_string: str = ""
    service_bus_queue_name: str = "order-hold-events"
    email_confirmation_enabled: bool = True
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = "no-reply@jojira.com"
    smtp_use_tls: bool = True
    postgres_enabled: bool = True
    postgres_host: str = "127.0.0.1"
    postgres_port: int = 5432
    postgres_db: str = "jojira_duffel"
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    postgres_url: str = ""
    message_broker: str = "rabbitmq"
    rabbitmq_host: str = "127.0.0.1"
    rabbitmq_port: int = 5672
    rabbitmq_user: str = "guest"
    rabbitmq_password: str = "guest"
    rabbitmq_queue_name: str = "order-hold-events"
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
                    if "force_instant_booking" in cfg_data:
                        self.force_instant_booking = bool(cfg_data["force_instant_booking"])
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
                    if "service_bus_enabled" in cfg_data:
                        self.service_bus_enabled = bool(cfg_data["service_bus_enabled"])
                    if "service_bus_connection_string" in cfg_data:
                        self.service_bus_connection_string = str(cfg_data["service_bus_connection_string"] or "")
                    if "service_bus_queue_name" in cfg_data and cfg_data["service_bus_queue_name"]:
                        self.service_bus_queue_name = str(cfg_data["service_bus_queue_name"])
                    if "email_confirmation_enabled" in cfg_data:
                        self.email_confirmation_enabled = bool(cfg_data["email_confirmation_enabled"])
                    if "smtp_host" in cfg_data and cfg_data["smtp_host"]:
                        self.smtp_host = str(cfg_data["smtp_host"])
                    if "smtp_port" in cfg_data and cfg_data["smtp_port"]:
                        self.smtp_port = int(cfg_data["smtp_port"])
                    if "smtp_username" in cfg_data:
                        self.smtp_username = str(cfg_data["smtp_username"] or "")
                    if "smtp_password" in cfg_data:
                        self.smtp_password = str(cfg_data["smtp_password"] or "")
                    if "smtp_from_email" in cfg_data and cfg_data["smtp_from_email"]:
                        self.smtp_from_email = str(cfg_data["smtp_from_email"])
                    if "smtp_use_tls" in cfg_data:
                        self.smtp_use_tls = bool(cfg_data["smtp_use_tls"])
                    if "postgres_enabled" in cfg_data:
                        self.postgres_enabled = bool(cfg_data["postgres_enabled"])
                    if "postgres_host" in cfg_data and cfg_data["postgres_host"]:
                        self.postgres_host = str(cfg_data["postgres_host"])
                    if "postgres_port" in cfg_data and cfg_data["postgres_port"]:
                        self.postgres_port = int(cfg_data["postgres_port"])
                    if "postgres_db" in cfg_data and cfg_data["postgres_db"]:
                        self.postgres_db = str(cfg_data["postgres_db"])
                    if "postgres_user" in cfg_data and cfg_data["postgres_user"]:
                        self.postgres_user = str(cfg_data["postgres_user"])
                    if "postgres_password" in cfg_data:
                        self.postgres_password = str(cfg_data["postgres_password"] or "")
                    if "postgres_url" in cfg_data:
                        self.postgres_url = str(cfg_data["postgres_url"] or "")
                    if "message_broker" in cfg_data and cfg_data["message_broker"]:
                        self.message_broker = str(cfg_data["message_broker"]).lower()
                    if "rabbitmq_host" in cfg_data and cfg_data["rabbitmq_host"]:
                        self.rabbitmq_host = str(cfg_data["rabbitmq_host"])
                    if "rabbitmq_port" in cfg_data and cfg_data["rabbitmq_port"]:
                        self.rabbitmq_port = int(cfg_data["rabbitmq_port"])
                    if "rabbitmq_user" in cfg_data and cfg_data["rabbitmq_user"]:
                        self.rabbitmq_user = str(cfg_data["rabbitmq_user"])
                    if "rabbitmq_password" in cfg_data:
                        self.rabbitmq_password = str(cfg_data["rabbitmq_password"] or "")
                    if "rabbitmq_queue_name" in cfg_data and cfg_data["rabbitmq_queue_name"]:
                        self.rabbitmq_queue_name = str(cfg_data["rabbitmq_queue_name"])
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

        # 2. Fall back to environment variable if empty
        if not self.api_token:
            self.api_token = os.environ.get("DUFFEL_API_TOKEN", "")
        if os.environ.get("MESSAGE_BROKER"):
            self.message_broker = os.environ["MESSAGE_BROKER"].lower()
        if os.environ.get("RABBITMQ_HOST"):
            self.rabbitmq_host = os.environ["RABBITMQ_HOST"]
        if os.environ.get("RABBITMQ_PORT"):
            self.rabbitmq_port = int(os.environ["RABBITMQ_PORT"])
        if os.environ.get("RABBITMQ_USER"):
            self.rabbitmq_user = os.environ["RABBITMQ_USER"]
        if os.environ.get("RABBITMQ_PASSWORD"):
            self.rabbitmq_password = os.environ["RABBITMQ_PASSWORD"]
        if os.environ.get("RABBITMQ_QUEUE_NAME"):
            self.rabbitmq_queue_name = os.environ["RABBITMQ_QUEUE_NAME"]
        if os.environ.get("AZURE_SERVICE_BUS_CONNECTION_STRING"):
            self.service_bus_connection_string = os.environ["AZURE_SERVICE_BUS_CONNECTION_STRING"]
        if os.environ.get("AZURE_SERVICE_BUS_QUEUE_NAME"):
            self.service_bus_queue_name = os.environ["AZURE_SERVICE_BUS_QUEUE_NAME"]
        if os.environ.get("SMTP_HOST"):
            self.smtp_host = os.environ["SMTP_HOST"]
        if os.environ.get("SMTP_PORT"):
            self.smtp_port = int(os.environ["SMTP_PORT"])
        if os.environ.get("SMTP_USERNAME"):
            self.smtp_username = os.environ["SMTP_USERNAME"]
        if os.environ.get("SMTP_PASSWORD"):
            self.smtp_password = os.environ["SMTP_PASSWORD"]
        if os.environ.get("POSTGRES_HOST"):
            self.postgres_host = os.environ["POSTGRES_HOST"]
        if os.environ.get("POSTGRES_PORT"):
            self.postgres_port = int(os.environ["POSTGRES_PORT"])
        if os.environ.get("POSTGRES_DB"):
            self.postgres_db = os.environ["POSTGRES_DB"]
        if os.environ.get("POSTGRES_USER"):
            self.postgres_user = os.environ["POSTGRES_USER"]
        if os.environ.get("POSTGRES_PASSWORD"):
            self.postgres_password = os.environ["POSTGRES_PASSWORD"]
        if os.environ.get("POSTGRES_URL") or os.environ.get("DATABASE_URL"):
            self.postgres_url = os.environ.get("POSTGRES_URL") or os.environ.get("DATABASE_URL", "")
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
        if os.environ.get("FORCE_INSTANT_BOOKING"):
            self.force_instant_booking = os.environ["FORCE_INSTANT_BOOKING"].strip().lower() in ("true", "1", "yes")

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
