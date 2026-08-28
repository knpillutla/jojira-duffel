#!/usr/bin/env bash
# ==============================================================================
# Azure Key Vault Secret Seeding & Update Script (Bash)
# Usage: ./set_keyvault_secrets.sh [dev|prod]
# ==============================================================================
set -euo pipefail

TARGET_ENV="${1:-dev}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/envs/${TARGET_ENV}.env"

if [ -f "${ENV_FILE}" ]; then
  source "${ENV_FILE}"
else
  echo "[ERROR] Config file '${ENV_FILE}' not found!"
  exit 1
fi

AKV_NAME="${AZURE_KEYVAULT_NAME}"
SUBSCRIPTION="${AZURE_SUBSCRIPTION_NAME:-${AZURE_SUBSCRIPTION_ID:-}}"

if [ -n "${SUBSCRIPTION}" ]; then
  az account set --subscription "${SUBSCRIPTION}"
fi

echo "=================================================================="
echo " Setting Azure Key Vault SECRETS for Vault: '${AKV_NAME}' (${TARGET_ENV})"
echo " Note: All sensitive values MUST be stored as SECRETS (not Keys)"
echo "=================================================================="

set_secret() {
  local name="$1"
  local val="$2"
  if [ -n "${val}" ]; then
    echo "  -> Setting Secret: '${name}'..."
    az keyvault secret set --vault-name "${AKV_NAME}" --name "${name}" --value "${val}" -o table
  fi
}

set_secret "duffel-api-token" "${DUFFEL_API_TOKEN:-}"
set_secret "openai-api-key" "${OPENAI_API_KEY:-}"
set_secret "gemini-api-key" "${GEMINI_API_KEY:-}"
set_secret "postgres-password" "${POSTGRES_PASSWORD:-}"
set_secret "service-bus-connection-string" "${SERVICE_BUS_CONNECTION_STRING:-}"

echo "=================================================================="
echo " [SUCCESS] Key Vault Secrets updated successfully in '${AKV_NAME}'"
echo "=================================================================="
