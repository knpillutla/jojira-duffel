#!/usr/bin/env bash
# ==============================================================================
# Script 3: Full Release Pipeline (Build Once -> Deploy DEV -> Deploy PROD)
# Usage:
#   ./pipeline_dev_to_prod.sh [image_tag]
# Example:
#   ./pipeline_dev_to_prod.sh v1.0.0
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TAG_INPUT="${1:-}"

if [ -z "${TAG_INPUT}" ]; then
  GIT_SHA=$(git rev-parse --short HEAD 2>/dev/null || echo "")
  if [ -n "${GIT_SHA}" ]; then
    TAG="${GIT_SHA}"
  else
    TAG="release-$(date +%Y%m%d-%H%M%S)"
  fi
else
  TAG="${TAG_INPUT}"
fi

echo "=================================================================="
echo " Starting Full End-to-End Release Pipeline (Build -> DEV -> PROD)"
echo " Image Release Tag: ${TAG}"
echo "=================================================================="

# Step 1: Build Docker image once and deploy to DEV environment
echo "[STAGE 1/2] Building image once & deploying to DEV..."
"${SCRIPT_DIR}/build_and_deploy_dev.sh" "${TAG}"

# Step 2: Promote exact same pre-built image to PROD environment
echo "[STAGE 2/2] Promoting pre-built image '${TAG}' to PROD..."
"${SCRIPT_DIR}/deploy_prod.sh" "${TAG}"

echo "=================================================================="
echo " [FULL PIPELINE SUCCESS] Release '${TAG}' successfully deployed to DEV & PROD!"
echo "=================================================================="
