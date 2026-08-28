"""
Configuration module for Jojira User Service.
"""

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Optional


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
        if Path(self.config_file).is_file():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
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
            except Exception:
                pass
