#!/usr/bin/env bash
# ==============================================================================
# "Build Once, Deploy Anywhere" Azure Container Apps Deployment Script
# Usage:
#   ./deploy.sh <env> [image_tag] [--build]
# Examples:
#   ./deploy.sh dev v1.0.0              # Deploy pre-built image v1.0.0 to dev
#   ./deploy.sh prod v1.0.0             # Deploy exact same image v1.0.0 to prod
#   ./deploy.sh dev v1.0.0 --build      # Build image once, then deploy to dev
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"

TARGET_ENV="${1:-dev}"
TAG_INPUT="${2:-}"

if [ -z "${TAG_INPUT}" ]; then
  GIT_SHA=$(git rev-parse --short HEAD 2>/dev/null || echo "")
  if [ -n "${GIT_SHA}" ]; then
    TAG="${GIT_SHA}"
  else
    TAG="dev-$(date +%Y%m%d-%H%M%S)"
  fi
else
  TAG="${TAG_INPUT}"
fi

DO_BUILD=false

for arg in "$@"; do
  if [ "$arg" == "--build" ]; then
    DO_BUILD=true
  fi
done

ENV_FILE="${SCRIPT_DIR}/envs/${TARGET_ENV}.env"

if [ -f "${ENV_FILE}" ]; then
  echo "[+] Loading environment configuration from: ${ENV_FILE}"
  source "${ENV_FILE}"
else
  echo "[ERROR] Environment config file not found at '${ENV_FILE}'"
  exit 1
fi

SUBSCRIPTION="${AZURE_SUBSCRIPTION_NAME:-${AZURE_SUBSCRIPTION_ID:-${AZURE_SUBSCRIPTION:-}}}"

ACR_SERVER="${AZURE_ACR_NAME}.azurecr.io"

echo "=================================================================="
echo " Starting Azure Container Apps Deployment (Build Once, Deploy Anywhere)"
echo " Target Environment: ${TARGET_ENV}"
echo " Subscription:       ${SUBSCRIPTION}"
echo " Image Tag:          ${TAG}"
echo " ACR Server:         ${ACR_SERVER}"
echo " Key Vault (AKV):    ${AZURE_KEYVAULT_NAME}"
echo "=================================================================="

# 1. Azure Authentication & Setup
echo "[1/5] Authenticating with Azure CLI..."
if [ -n "${SUBSCRIPTION}" ]; then
  az account set --subscription "${SUBSCRIPTION}" || true
fi
az extension add --name containerapp --upgrade --yes --allow-preview true

# 2. Build Stage (Only executed if --build flag is explicitly passed)
if [ "${DO_BUILD}" = true ]; then
  echo "[2/5] [--build flag set] Building Docker images for Booking, User, and Order microservices..."
  az acr login --name "${AZURE_ACR_NAME}"

  echo "      [1/3] Building Booking API image (${ACR_SERVER}/jojira-api:${TAG})..."
  docker build -t "${ACR_SERVER}/jojira-api:${TAG}" -f "${ROOT_DIR}/Dockerfile.booking-service" "${ROOT_DIR}"
  docker push "${ACR_SERVER}/jojira-api:${TAG}"

  echo "      [2/3] Building User Service image (${ACR_SERVER}/jojira-user-service:${TAG})..."
  docker build -t "${ACR_SERVER}/jojira-user-service:${TAG}" -f "${ROOT_DIR}/Dockerfile.user-service" "${ROOT_DIR}"
  docker push "${ACR_SERVER}/jojira-user-service:${TAG}"

  echo "      [3/3] Building Order Service image (${ACR_SERVER}/jojira-order-service:${TAG})..."
  docker build -t "${ACR_SERVER}/jojira-order-service:${TAG}" -f "${ROOT_DIR}/Dockerfile.order-service" "${ROOT_DIR}"
  docker push "${ACR_SERVER}/jojira-order-service:${TAG}"
else
  echo "[2/5] Skipping build step. Reusing pre-built image artifacts for Booking, User, and Order..."
fi

# 3. Ensure Container Apps Environment Exist
echo "[3/5] Ensuring Resource Group & Container Apps Environment in '${TARGET_ENV}'..."
az group create --name "${AZURE_RESOURCE_GROUP}" --location "${AZURE_LOCATION}" -o table

if ! az containerapp env show --name "${AZURE_CONTAINER_APP_ENV}" --resource-group "${AZURE_RESOURCE_GROUP}" >/dev/null 2>&1; then
  az containerapp env create \
    --name "${AZURE_CONTAINER_APP_ENV}" \
    --resource-group "${AZURE_RESOURCE_GROUP}" \
    --location "${AZURE_LOCATION}"
fi

ACR_PASSWORD=$(az acr credential show --name "${AZURE_ACR_NAME}" --query "passwords[0].value" -o tsv 2>/dev/null || echo "")

# 4. Deploy Main API Container App (Injecting Environment-Specific Configs & Secret Vault)
echo "[4/5] Deploying '${CONTAINER_APP_API_NAME}' with environment configs from '${TARGET_ENV}.env'..."
az containerapp create \
  --name "${CONTAINER_APP_API_NAME}" \
  --resource-group "${AZURE_RESOURCE_GROUP}" \
  --environment "${AZURE_CONTAINER_APP_ENV}" \
  --image "${ACR_SERVER}/jojira-api:${TAG}" \
  --registry-server "${ACR_SERVER}" \
  --registry-username "${AZURE_ACR_NAME}" \
  --registry-password "${ACR_PASSWORD}" \
  --target-port 8000 \
  --ingress external \
  --cpu "${CPU:-0.5}" \
  --memory "${MEMORY:-1.0Gi}" \
  --min-replicas "${MIN_REPLICAS:-0}" \
  --max-replicas "${MAX_REPLICAS:-10}" \
  --env-vars \
    ENVIRONMENT="${TARGET_ENV}" \
    AZURE_KEYVAULT_ENABLED="${AZURE_KEYVAULT_ENABLED:-true}" \
    AZURE_KEYVAULT_NAME="${AZURE_KEYVAULT_NAME}" \
    AZURE_KEYVAULT_URL="https://${AZURE_KEYVAULT_NAME}.vault.azure.net/" \
    DEFAULT_ORDER_MODE="${DEFAULT_ORDER_MODE:-instant}" \
    LLM_PROVIDER="${LLM_PROVIDER:-openai}" \
  --system-assigned

# 5. Deploy User Service & Order Service Container Apps
echo "[5/5] Deploying User Service & Order Service Container Apps..."
az containerapp create \
  --name "${CONTAINER_APP_USER_SERVICE_NAME}" \
  --resource-group "${AZURE_RESOURCE_GROUP}" \
  --environment "${AZURE_CONTAINER_APP_ENV}" \
  --image "${ACR_SERVER}/jojira-user-service:${TAG}" \
  --registry-server "${ACR_SERVER}" \
  --registry-username "${AZURE_ACR_NAME}" \
  --registry-password "${ACR_PASSWORD}" \
  --target-port 8001 \
  --ingress external \
  --cpu "${CPU:-0.25}" \
  --memory "${MEMORY:-0.5Gi}" \
  --min-replicas "${MIN_REPLICAS:-0}" \
  --max-replicas "${MAX_REPLICAS:-10}" \
  --env-vars \
    ENVIRONMENT="${TARGET_ENV}" \
    AZURE_KEYVAULT_ENABLED="${AZURE_KEYVAULT_ENABLED:-true}" \
    AZURE_KEYVAULT_NAME="${AZURE_KEYVAULT_NAME}" \
    AZURE_KEYVAULT_URL="https://${AZURE_KEYVAULT_NAME}.vault.azure.net/" \
  --system-assigned

az containerapp create \
  --name "${CONTAINER_APP_ORDER_SERVICE_NAME}" \
  --resource-group "${AZURE_RESOURCE_GROUP}" \
  --environment "${AZURE_CONTAINER_APP_ENV}" \
  --image "${ACR_SERVER}/jojira-order-service:${TAG}" \
  --registry-server "${ACR_SERVER}" \
  --registry-username "${AZURE_ACR_NAME}" \
  --registry-password "${ACR_PASSWORD}" \
  --ingress disabled \
  --cpu "${CPU:-0.25}" \
  --memory "${MEMORY:-0.5Gi}" \
  --min-replicas "${MIN_REPLICAS:-0}" \
  --max-replicas "${MAX_REPLICAS:-10}" \
  --env-vars \
    ENVIRONMENT="${TARGET_ENV}" \
    AZURE_KEYVAULT_ENABLED="${AZURE_KEYVAULT_ENABLED:-true}" \
    AZURE_KEYVAULT_NAME="${AZURE_KEYVAULT_NAME}" \
    AZURE_KEYVAULT_URL="https://${AZURE_KEYVAULT_NAME}.vault.azure.net/" \
  --system-assigned

API_URL=$(az containerapp show --name "${CONTAINER_APP_API_NAME}" --resource-group "${AZURE_RESOURCE_GROUP}" --query "properties.configuration.ingress.fqdn" -o tsv)

echo "=================================================================="
echo " [SUCCESS] Deployed image '${TAG}' to '${TARGET_ENV}' environment!"
echo " Main REST API URL: https://${API_URL}"
echo "=================================================================="
