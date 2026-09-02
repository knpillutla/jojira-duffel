"""
Configuration module for the Duffel API Python client.
"""

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Optional


def _find_file(rel_path: str) -> Optional[Path]:
    """Resolve a file path checking absolute/CWD path, project root, and parent directories."""
    if not rel_path:
        return None
    p = Path(rel_path)
    if p.is_file():
        return p.resolve()
    project_root = Path(__file__).resolve().parent.parent.parent
    candidate = project_root / rel_path
    if candidate.is_file():
        return candidate.resolve()
    for parent in Path(__file__).resolve().parents:
        cand = parent / rel_path
        if cand.is_file():
            return cand.resolve()
    cwd_cand = Path.cwd() / rel_path
    if cwd_cand.is_file():
        return cwd_cand.resolve()
    return None


_LOADED_JSON_CACHE: dict[str, dict] = {}
_LOGGED_CONFIG_PATHS: set[str] = set()


def _read_json_file(file_path: Path, log_type: str = "CONFIG") -> Optional[dict]:
    """Reads and parses a JSON file with in-memory caching and once-only load notification."""
    path_str = str(file_path.resolve())
    if path_str in _LOADED_JSON_CACHE:
        return _LOADED_JSON_CACHE[path_str]
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            _LOADED_JSON_CACHE[path_str] = data
            if path_str not in _LOGGED_CONFIG_PATHS:
                _LOGGED_CONFIG_PATHS.add(path_str)
                print(f"[{log_type}] Loaded configuration from '{path_str}'")
            return data
    except Exception as err:
        print(f"[{log_type} ERROR] Failed loading configuration from '{path_str}': {err}")
        return None


@dataclass
class DuffelConfig:
    """Configuration options for Duffel API client."""
    environment: str = "local"
    test_mode: bool = False
    api_token: str = ""
    base_url: str = "https://api.duffel.com"
    api_version: str = "v2"
    timeout: float = 120.0
    force_instant_booking: bool = False
    default_order_mode: str = "hold"
    azure_keyvault_enabled: bool = False
    azure_keyvault_name: str = ""
    azure_keyvault_url: str = ""
    user_service_url: str = ""
    order_service_url: str = ""
    booking_service_url: str = ""
    api_gateway_url: str = ""
    user_service_port: int = 5000
    debug: bool = False
    enable_web_scrapers: bool = False
    enable_cache: bool = True
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None
    cache_ttl_seconds: int = 3600
    max_cached_offers: int = 40
    max_non_stop_offers: int = 10
    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-flash"
    gemini_extraction_model: str = "gemini-1.5-flash"
    gemini_planner_model: str = "gemini-1.5-pro"
    gemini_enabled: bool = True
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_extraction_model: str = "gpt-4o-mini"
    openai_planner_model: str = "gpt-4o"
    openai_enabled: bool = True
    llm_provider: str = "openai"
    llm_extraction_provider: str = "openai"
    llm_planner_provider: str = "openai"

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
    rate_limit_delay_seconds: float = 0.25
    config_file: str = "config.json"
    system_prompts_file: str = "system_prompts.json"
    system_prompts: Optional[dict[str, str]] = None

    def __post_init__(self):
        if self.retry_status_codes is None:
            self.retry_status_codes = [500, 502, 503, 504, 429]
        if self.system_prompts is None:
            self.system_prompts = {}

        # Load system_prompts.json if present
        sp_path = _find_file(self.system_prompts_file) or _find_file("system_prompts.json")
        if sp_path and sp_path.is_file():
            sp_data = _read_json_file(sp_path, log_type="PROMPTS")
            if sp_data:
                self.system_prompts = sp_data

        # 1. Load from environment-specific JSON config file if present
        env_name = os.getenv("ENVIRONMENT", "").lower().strip()
        custom_config_path = os.getenv("CONFIG_FILE_PATH", "")

        target_file_path: Optional[Path] = None
        if custom_config_path:
            target_file_path = _find_file(custom_config_path)

        # Check config.local.json first for developer local overrides
        if not target_file_path:
            target_file_path = _find_file("config.local.json")

        # Check environment-specific config files if specified
        if not target_file_path and env_name:
            target_file_path = (
                _find_file(f"deploy/container_apps/configs/config.{env_name}.json")
                or _find_file(f"config.{env_name}.json")
            )

        # Fallback to configured config_file or config.json
        if not target_file_path and self.config_file:
            target_file_path = (
                _find_file(self.config_file)
                or _find_file("config.json")
            )

        if target_file_path and target_file_path.is_file():
            cfg_data = _read_json_file(target_file_path, log_type="CONFIG") or {}
            if cfg_data:
                if "environment" in cfg_data and cfg_data["environment"]:
                    self.environment = str(cfg_data["environment"]).strip()
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
                if "default_order_mode" in cfg_data and cfg_data["default_order_mode"]:
                    self.default_order_mode = str(cfg_data["default_order_mode"]).lower().strip()
                elif "default_booking_mode" in cfg_data and cfg_data["default_booking_mode"]:
                    self.default_order_mode = str(cfg_data["default_booking_mode"]).lower().strip()
                if "azure_keyvault_enabled" in cfg_data:
                    self.azure_keyvault_enabled = bool(cfg_data["azure_keyvault_enabled"])
                if "azure_keyvault_name" in cfg_data and cfg_data["azure_keyvault_name"]:
                    self.azure_keyvault_name = str(cfg_data["azure_keyvault_name"]).strip()
                if "azure_keyvault_url" in cfg_data and cfg_data["azure_keyvault_url"]:
                    self.azure_keyvault_url = str(cfg_data["azure_keyvault_url"]).strip()
                if "user_service_url" in cfg_data and cfg_data["user_service_url"]:
                    self.user_service_url = str(cfg_data["user_service_url"]).strip()
                if "order_service_url" in cfg_data and cfg_data["order_service_url"]:
                    self.order_service_url = str(cfg_data["order_service_url"]).strip()
                if "booking_service_url" in cfg_data and cfg_data["booking_service_url"]:
                    self.booking_service_url = str(cfg_data["booking_service_url"]).strip()
                if "api_gateway_url" in cfg_data and cfg_data["api_gateway_url"]:
                    self.api_gateway_url = str(cfg_data["api_gateway_url"]).strip()
                if "debug" in cfg_data:
                    self.debug = bool(cfg_data["debug"])
                if "test_mode" in cfg_data:
                    self.test_mode = bool(cfg_data["test_mode"])
                if "enable_web_scrapers" in cfg_data:
                    self.enable_web_scrapers = bool(cfg_data["enable_web_scrapers"])
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
                if "gemini_extraction_model" in cfg_data and cfg_data["gemini_extraction_model"]:
                    self.gemini_extraction_model = str(cfg_data["gemini_extraction_model"])
                if "gemini_planner_model" in cfg_data and cfg_data["gemini_planner_model"]:
                    self.gemini_planner_model = str(cfg_data["gemini_planner_model"])
                elif "gemini_travel_model" in cfg_data and cfg_data["gemini_travel_model"]:
                    self.gemini_planner_model = str(cfg_data["gemini_travel_model"])
                if "gemini_enabled" in cfg_data:
                    self.gemini_enabled = bool(cfg_data["gemini_enabled"])
                if "openai_api_key" in cfg_data:
                    self.openai_api_key = str(cfg_data["openai_api_key"] or "")
                if "openai_model" in cfg_data and cfg_data["openai_model"]:
                    self.openai_model = str(cfg_data["openai_model"])
                if "openai_extraction_model" in cfg_data and cfg_data["openai_extraction_model"]:
                    self.openai_extraction_model = str(cfg_data["openai_extraction_model"])
                elif "openai_intent_model" in cfg_data and cfg_data["openai_intent_model"]:
                    self.openai_extraction_model = str(cfg_data["openai_intent_model"])
                if "openai_planner_model" in cfg_data and cfg_data["openai_planner_model"]:
                    self.openai_planner_model = str(cfg_data["openai_planner_model"])
                elif "openai_travel_model" in cfg_data and cfg_data["openai_travel_model"]:
                    self.openai_planner_model = str(cfg_data["openai_travel_model"])
                elif "openai_itinerary_model" in cfg_data and cfg_data["openai_itinerary_model"]:
                    self.openai_planner_model = str(cfg_data["openai_itinerary_model"])
                if "openai_enabled" in cfg_data:
                    self.openai_enabled = bool(cfg_data["openai_enabled"])
                if "llm_provider" in cfg_data and cfg_data["llm_provider"]:
                    self.llm_provider = str(cfg_data["llm_provider"]).lower()
                if "llm_extraction_provider" in cfg_data and cfg_data["llm_extraction_provider"]:
                    self.llm_extraction_provider = str(cfg_data["llm_extraction_provider"]).lower()
                elif "llm_intent_provider" in cfg_data and cfg_data["llm_intent_provider"]:
                    self.llm_extraction_provider = str(cfg_data["llm_intent_provider"]).lower()
                if "llm_planner_provider" in cfg_data and cfg_data["llm_planner_provider"]:
                    self.llm_planner_provider = str(cfg_data["llm_planner_provider"]).lower()
                elif "llm_travel_provider" in cfg_data and cfg_data["llm_travel_provider"]:
                    self.llm_planner_provider = str(cfg_data["llm_travel_provider"]).lower()
                elif "llm_itinerary_provider" in cfg_data and cfg_data["llm_itinerary_provider"]:
                    self.llm_planner_provider = str(cfg_data["llm_itinerary_provider"]).lower()
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
                if "rate_limit_delay_seconds" in cfg_data and cfg_data["rate_limit_delay_seconds"] is not None:
                    self.rate_limit_delay_seconds = float(cfg_data["rate_limit_delay_seconds"])

        # 2. Apply environment variable overrides
        if os.environ.get("RATE_LIMIT_DELAY_SECONDS"):
            try:
                self.rate_limit_delay_seconds = float(os.environ["RATE_LIMIT_DELAY_SECONDS"])
            except Exception:
                pass
        is_local_mode = (target_file_path and "local" in target_file_path.name.lower()) or self.environment == "local"

        if not self.api_token or os.environ.get("DUFFEL_API_TOKEN"):
            self.api_token = os.environ.get("DUFFEL_API_TOKEN") or os.environ.get("DUFFEL_TOKEN") or os.environ.get("API_TOKEN") or self.api_token
        if os.environ.get("DUFFEL_TIMEOUT") or os.environ.get("TIMEOUT"):
            try:
                self.timeout = float(os.environ.get("DUFFEL_TIMEOUT") or os.environ["TIMEOUT"])
            except Exception:
                pass
        if os.environ.get("TEST_MODE"):
            self.test_mode = os.environ["TEST_MODE"].strip().lower() in ("1", "true", "yes")
        if os.environ.get("DUFFEL_DEBUG") or os.environ.get("DEBUG"):
            debug_val = (os.environ.get("DUFFEL_DEBUG") or os.environ.get("DEBUG") or "").strip().lower()
            self.debug = debug_val in ("1", "true", "yes")
        if os.environ.get("MESSAGE_BROKER"):
            self.message_broker = os.environ["MESSAGE_BROKER"].lower()
        if os.environ.get("REDIS_HOST"):
            self.redis_host = os.environ["REDIS_HOST"].strip()
        if os.environ.get("REDIS_PORT"):
            self.redis_port = int(os.environ["REDIS_PORT"])
        if os.environ.get("REDIS_PASSWORD"):
            self.redis_password = os.environ["REDIS_PASSWORD"]
        if os.environ.get("REDIS_URL"):
            r_url = os.environ["REDIS_URL"].strip()
            try:
                from urllib.parse import urlparse
                parsed_r = urlparse(r_url)
                if parsed_r.hostname:
                    self.redis_host = parsed_r.hostname
                if parsed_r.port:
                    self.redis_port = parsed_r.port
                if parsed_r.password:
                    self.redis_password = parsed_r.password
            except Exception:
                pass

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
        if os.environ.get("GEMINI_EXTRACTION_MODEL") or os.environ.get("GEMINI_INTENT_MODEL"):
            self.gemini_extraction_model = os.environ.get("GEMINI_EXTRACTION_MODEL") or os.environ["GEMINI_INTENT_MODEL"]
        if os.environ.get("GEMINI_PLANNER_MODEL") or os.environ.get("GEMINI_TRAVEL_MODEL") or os.environ.get("GEMINI_ITINERARY_MODEL"):
            self.gemini_planner_model = os.environ.get("GEMINI_PLANNER_MODEL") or os.environ.get("GEMINI_TRAVEL_MODEL") or os.environ["GEMINI_ITINERARY_MODEL"]
        if not self.openai_api_key:
            self.openai_api_key = os.environ.get("OPENAI_API_KEY", "")
        if os.environ.get("OPENAI_MODEL"):
            self.openai_model = os.environ["OPENAI_MODEL"]
        if os.environ.get("OPENAI_EXTRACTION_MODEL") or os.environ.get("OPENAI_INTENT_MODEL"):
            self.openai_extraction_model = os.environ.get("OPENAI_EXTRACTION_MODEL") or os.environ["OPENAI_INTENT_MODEL"]
        if os.environ.get("OPENAI_PLANNER_MODEL") or os.environ.get("OPENAI_TRAVEL_MODEL") or os.environ.get("OPENAI_ITINERARY_MODEL"):
            self.openai_planner_model = os.environ.get("OPENAI_PLANNER_MODEL") or os.environ.get("OPENAI_TRAVEL_MODEL") or os.environ["OPENAI_ITINERARY_MODEL"]
        if os.environ.get("LLM_PROVIDER"):
            self.llm_provider = os.environ["LLM_PROVIDER"].lower()
        if os.environ.get("LLM_EXTRACTION_PROVIDER") or os.environ.get("LLM_INTENT_PROVIDER"):
            self.llm_extraction_provider = (os.environ.get("LLM_EXTRACTION_PROVIDER") or os.environ["LLM_INTENT_PROVIDER"]).lower()
        if os.environ.get("LLM_PLANNER_PROVIDER") or os.environ.get("LLM_TRAVEL_PROVIDER") or os.environ.get("LLM_ITINERARY_PROVIDER"):
            self.llm_planner_provider = (os.environ.get("LLM_PLANNER_PROVIDER") or os.environ.get("LLM_TRAVEL_PROVIDER") or os.environ["LLM_ITINERARY_PROVIDER"]).lower()
        if os.environ.get("DUFFEL_MAX_RETRIES"):
            self.max_retries = int(os.environ["DUFFEL_MAX_RETRIES"])
        if os.environ.get("FORCE_INSTANT_BOOKING"):
            self.force_instant_booking = os.environ["FORCE_INSTANT_BOOKING"].strip().lower() in ("true", "1", "yes")

        # Azure Key Vault enablement: strictly suppressed if local config is loaded unless local config explicitly enabled it
        if is_local_mode:
            if target_file_path and "azure_keyvault_enabled" in cfg_data:
                self.azure_keyvault_enabled = bool(cfg_data["azure_keyvault_enabled"])
            else:
                self.azure_keyvault_enabled = False
        else:
            if os.environ.get("AZURE_KEYVAULT_ENABLED"):
                self.azure_keyvault_enabled = os.environ["AZURE_KEYVAULT_ENABLED"].strip().lower() in ("true", "1", "yes")

        if os.environ.get("AZURE_KEYVAULT_NAME"):
            self.azure_keyvault_name = os.environ["AZURE_KEYVAULT_NAME"].strip()
        if os.environ.get("AZURE_KEYVAULT_URL"):
            self.azure_keyvault_url = os.environ["AZURE_KEYVAULT_URL"].strip()
        # Service URLs: Uses Azure environment variables when deployed, defaults to localhost locally
        self.user_service_url = os.getenv("USER_SERVICE_URL", self.user_service_url or "http://localhost:8001").strip()
        self.order_service_url = os.getenv("ORDER_SERVICE_URL", self.order_service_url or "http://localhost:8000").strip()
        self.booking_service_url = os.getenv("BOOKING_SERVICE_URL", self.booking_service_url or "http://localhost:8000").strip()
        self.api_gateway_url = os.getenv("API_GATEWAY_URL", self.api_gateway_url or "http://localhost:8000").strip()
        self.user_service_port = int(os.getenv("PORT", getattr(self, "user_service_port", 8001)))

        # 3. Load secrets from Azure Key Vault if explicitly enabled
        if self.azure_keyvault_enabled:
            try:
                from .azure_vault import AzureKeyVaultClient
                AzureKeyVaultClient.load_secrets_into_config(self)
            except Exception as kv_err:
                print(f"[AZURE KEY VAULT NOTICE] Azure Key Vault secret loading notice: {kv_err}")

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
