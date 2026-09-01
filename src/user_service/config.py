"""
Configuration module for Jojira User Service.
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


_LOADED_USER_CONFIG_CACHE: dict[str, dict] = {}
_LOGGED_USER_CONFIG_PATHS: set[str] = set()


def _read_json_file(file_path: Path, log_type: str = "USER_SERVICE CONFIG") -> Optional[dict]:
    """Reads and parses a JSON file with in-memory caching and once-only load notification."""
    path_str = str(file_path.resolve())
    if path_str in _LOADED_USER_CONFIG_CACHE:
        return _LOADED_USER_CONFIG_CACHE[path_str]
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            _LOADED_USER_CONFIG_CACHE[path_str] = data
            if path_str not in _LOGGED_USER_CONFIG_PATHS:
                _LOGGED_USER_CONFIG_PATHS.add(path_str)
                print(f"[{log_type}] Loaded configuration from '{path_str}'")
            return data
    except Exception as err:
        print(f"[{log_type} ERROR] Failed loading configuration from '{path_str}': {err}")
        return None


@dataclass
class UserServiceConfig:
    """Configuration options for User Service."""
    postgres_enabled: bool = True
    postgres_host: str = "127.0.0.1"
    postgres_port: int = 5432
    postgres_db: str = "jojira_user_service"
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    postgres_url: str = ""
    jwt_secret: str = "jojira_user_service_jwt_secret_2026"
    jwt_algorithm: str = "HS256"
    google_client_id: str = "902031561179-a55usf1op5d3sukbm6vr1c2uqs0k6t95.apps.googleusercontent.com"
    google_client_secret: str = ""
    config_file: str = "config.json"

    def __post_init__(self):
        target_file_path = _find_file("config.local.json") or _find_file(self.config_file)
        if target_file_path and target_file_path.is_file():
            data = _read_json_file(target_file_path, log_type="USER_SERVICE CONFIG") or {}
            if data:
                if "google_client_id" in data and data["google_client_id"]:
                    self.google_client_id = str(data["google_client_id"])
                if "google_client_secret" in data and data["google_client_secret"]:
                    self.google_client_secret = str(data["google_client_secret"])

                if "postgres_enabled" in data:
                    self.postgres_enabled = bool(data["postgres_enabled"])
                if "postgres_host" in data and data["postgres_host"]:
                    self.postgres_host = str(data["postgres_host"])
                if "postgres_port" in data:
                    self.postgres_port = int(data["postgres_port"])
                if "postgres_db" in data and data["postgres_db"]:
                    self.postgres_db = str(data["postgres_db"])
                if "postgres_user" in data and data["postgres_user"]:
                    self.postgres_user = str(data["postgres_user"])
                if "postgres_password" in data and data["postgres_password"]:
                    self.postgres_password = str(data["postgres_password"])
                if "postgres_url" in data and data["postgres_url"]:
                    self.postgres_url = str(data["postgres_url"])
                if "jwt_secret" in data and data["jwt_secret"]:
                    self.jwt_secret = str(data["jwt_secret"])
