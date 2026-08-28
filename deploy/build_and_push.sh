#!/usr/bin/env bash
# ==============================================================================
# Build Docker Images & Push to Azure Container Registry (ACR)
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Load configuration variables
if [ -f "${SCRIPT_DIR}/config.env" ]; then
  source "${SCRIPT_DIR}/config.env"
else
  echo "[ERROR] ${SCRIPT_DIR}/config.env file not found!"
  exit 1
fi

# Generate dynamic Git SHA tag if available
GIT_SHA=$(git rev-parse --short HEAD 2>/dev/null || echo "latest")
TAG="${IMAGE_TAG:-$GIT_SHA}"
ACR_LOGIN_SERVER="${AZURE_ACR_NAME}.azurecr.io"

echo "=================================================================="
echo " Starting Build & Push to Azure Container Registry"
echo " Resource Group: ${AZURE_RESOURCE_GROUP}"
echo " ACR Name:       ${AZURE_ACR_NAME} (${ACR_LOGIN_SERVER})"
echo " Image Tag:      ${TAG}"
echo "=================================================================="

# 1. Login to Azure & ACR
echo "[1/4] Authenticating with Azure ACR..."
az account set --subscription "${AZURE_SUBSCRIPTION_ID}" || true
az acr login --name "${AZURE_ACR_NAME}"

# 2. Build & Push API Image (Main REST API)
echo "[2/4] Building & Pushing jojira-api image..."
docker build -t "${ACR_LOGIN_SERVER}/jojira-api:${TAG}" -t "${ACR_LOGIN_SERVER}/jojira-api:latest" -f "${ROOT_DIR}/Dockerfile" "${ROOT_DIR}"
docker push "${ACR_LOGIN_SERVER}/jojira-api:${TAG}"
docker push "${ACR_LOGIN_SERVER}/jojira-api:latest"

# 3. Build & Push User Service Image
echo "[3/4] Building & Pushing jojira-user-service image..."
docker build -t "${ACR_LOGIN_SERVER}/jojira-user-service:${TAG}" -t "${ACR_LOGIN_SERVER}/jojira-user-service:latest" -f "${ROOT_DIR}/Dockerfile" "${ROOT_DIR}"
docker push "${ACR_LOGIN_SERVER}/jojira-user-service:${TAG}"
docker push "${ACR_LOGIN_SERVER}/jojira-user-service:latest"

# 4. Build & Push Order Service Worker Image
echo "[4/4] Building & Pushing jojira-order-service image..."
docker build -t "${ACR_LOGIN_SERVER}/jojira-order-service:${TAG}" -t "${ACR_LOGIN_SERVER}/jojira-order-service:latest" -f "${ROOT_DIR}/Dockerfile.order-service" "${ROOT_DIR}"
docker push "${ACR_LOGIN_SERVER}/jojira-order-service:${TAG}"
docker push "${ACR_LOGIN_SERVER}/jojira-order-service:latest"

echo "=================================================================="
echo " [SUCCESS] Images successfully built & pushed to ${ACR_LOGIN_SERVER}!"
echo " Tags pushed: ${TAG}, latest"
echo "=================================================================="
