"""
Azure Key Vault Secrets Manager for Jojira Duffel API.
Provides decoupled, single-responsibility loading of API secrets and credentials from Azure Key Vault.
"""

import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)


class AzureKeyVaultClient:
    """
    Client for interacting with Azure Key Vault to securely retrieve production API keys and credentials.
    """

    SECRET_MAPPINGS = {
        "duffel-api-token": "api_token",
        "DUFFEL-API-TOKEN": "api_token",
        "openai-api-key": "openai_api_key",
        "OPENAI-API-KEY": "openai_api_key",
        "gemini-api-key": "gemini_api_key",
        "GEMINI-API-KEY": "gemini_api_key",
        "postgres-password": "postgres_password",
        "POSTGRES-PASSWORD": "postgres_password",
        "rabbitmq-password": "rabbitmq_password",
        "RABBITMQ-PASSWORD": "rabbitmq_password",
        "smtp-password": "smtp_password",
        "SMTP-PASSWORD": "smtp_password",
        "google-client-secret": "google_client_secret",
        "GOOGLE-CLIENT-SECRET": "google_client_secret",
        "service-bus-connection-string": "service_bus_connection_string",
    }

    def __init__(self, vault_name: str = "", vault_url: str = ""):
        self.vault_name = vault_name or os.getenv("AZURE_KEYVAULT_NAME", "")
        self.vault_url = vault_url or os.getenv("AZURE_KEYVAULT_URL", "")

        if not self.vault_url and self.vault_name:
            self.vault_url = f"https://{self.vault_name}.vault.azure.net/"

        self._client = None

    def _get_client(self):
        if self._client:
            return self._client

        if not self.vault_url:
            raise ValueError("[AZURE KEY VAULT ERROR] Vault URL or Vault Name must be specified when Azure Key Vault is enabled.")

        try:
            from azure.identity import DefaultAzureCredential
            from azure.keyvault.secrets import SecretClient

            credential = DefaultAzureCredential()
            self._client = SecretClient(vault_url=self.vault_url, credential=credential)
            return self._client
        except ImportError as imp_err:
            err_msg = (
                "[AZURE KEY VAULT ERROR] Azure SDK libraries 'azure-identity' and 'azure-keyvault-secrets' "
                f"are required to fetch secrets from Azure Key Vault: {imp_err}"
            )
            logger.error(err_msg)
            print(f"\n{'=' * 80}\n{err_msg}\n{'=' * 80}\n")
            raise RuntimeError(err_msg) from imp_err
        except Exception as err:
            err_msg = f"[AZURE KEY VAULT ERROR] Failed initializing SecretClient for '{self.vault_url}': {err}"
            logger.error(err_msg)
            print(f"\n{'=' * 80}\n{err_msg}\n{'=' * 80}\n")
            raise RuntimeError(err_msg) from err

    def get_secret(self, secret_name: str) -> Optional[str]:
        """Fetch a single secret value from Azure Key Vault by secret name."""
        client = self._get_client()
        try:
            secret = client.get_secret(secret_name)
            return secret.value if secret else None
        except Exception as err:
            logger.warning(f"[AZURE KEY VAULT NOTICE] Could not retrieve secret '{secret_name}' from {self.vault_url}: {err}")
            return None

    def fetch_all_secrets(self) -> dict[str, str]:
        """Fetch all recognized application secrets from Azure Key Vault."""
        secrets_found = {}
        for vault_key, target_attr in self.SECRET_MAPPINGS.items():
            if target_attr in secrets_found and secrets_found[target_attr]:
                continue
            val = self.get_secret(vault_key)
            if val:
                secrets_found[target_attr] = val
        return secrets_found

    @classmethod
    def load_secrets_into_config(cls, config: Any) -> bool:
        """
        Loads secrets from Azure Key Vault and injects them into the DuffelConfig instance.
        """
        vault_name = getattr(config, "azure_keyvault_name", "") or os.getenv("AZURE_KEYVAULT_NAME", "")
        vault_url = getattr(config, "azure_keyvault_url", "") or os.getenv("AZURE_KEYVAULT_URL", "")

        vault_client = cls(vault_name=vault_name, vault_url=vault_url)
        print(f"\n[AZURE KEY VAULT] Fetching production secrets from Vault URL: '{vault_client.vault_url}'...")

        fetched_secrets = vault_client.fetch_all_secrets()
        if not fetched_secrets:
            print(f"[AZURE KEY VAULT NOTICE] Connected to '{vault_client.vault_url}' but no secrets were loaded.")
            return False

        loaded_count = 0
        for attr_name, secret_val in fetched_secrets.items():
            if hasattr(config, attr_name) and secret_val:
                setattr(config, attr_name, secret_val)
                loaded_count += 1
                print(f"  * Loaded secret '{attr_name}' from Azure Key Vault.")

        print(f"[AZURE KEY VAULT SUCCESS] Loaded {loaded_count} secrets from Azure Key Vault into application config.\n")
        return True
