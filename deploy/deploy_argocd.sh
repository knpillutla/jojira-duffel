#!/usr/bin/env bash
# ==============================================================================
# Connect to Azure AKS & Deploy ArgoCD Application Manifest
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Load variables
if [ -f "${SCRIPT_DIR}/config.env" ]; then
  source "${SCRIPT_DIR}/config.env"
fi

echo "=================================================================="
echo " Connecting to Azure AKS Cluster & Registering ArgoCD App"
echo " Resource Group: ${AZURE_RESOURCE_GROUP}"
echo " AKS Cluster:    ${AZURE_AKS_CLUSTER}"
echo " ArgoCD App:     ${ARGOCD_APP_NAME}"
echo " Git Repository: ${ARGOCD_GIT_REPO_URL}"
echo "=================================================================="

# 1. Connect kubectl context to Azure AKS
echo "[1/3] Fetching AKS Credentials..."
az aks get-credentials --resource-group "${AZURE_RESOURCE_GROUP}" --name "${AZURE_AKS_CLUSTER}" --overwrite-existing

# 2. Ensure target namespace exists
echo "[2/3] Preparing Kubernetes namespace '${K8S_NAMESPACE}'..."
kubectl create namespace "${K8S_NAMESPACE}" --dry-run=client -o yaml | kubectl apply -f -

# 3. Apply ArgoCD Application Manifest
echo "[3/3] Registering Application in ArgoCD..."
kubectl apply -f "${SCRIPT_DIR}/argocd/application.yaml"

echo "=================================================================="
echo " [SUCCESS] ArgoCD Application registered successfully!"
echo " ArgoCD is now continuously syncing '${ARGOCD_GIT_PATH}' from Git!"
echo " Check status with: kubectl get application ${ARGOCD_APP_NAME} -n ${ARGOCD_NAMESPACE}"
echo "=================================================================="
