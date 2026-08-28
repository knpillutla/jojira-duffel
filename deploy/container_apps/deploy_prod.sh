#!/usr/bin/env bash
# ==============================================================================
# Script 2: Deploy Pre-Built Docker Image Artifact to PROD Environment
# Usage:
#   ./deploy_prod.sh [image_tag]
# Example:
#   ./deploy_prod.sh v1.0.0
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TAG_INPUT="${1:-}"

if [ -z "${TAG_INPUT}" ]; then
  GIT_SHA=$(git rev-parse --short HEAD 2>/dev/null || echo "")
  if [ -n "${GIT_SHA}" ]; then
    TAG="${GIT_SHA}"
  else
    TAG="prod-$(date +%Y%m%d-%H%M%S)"
  fi
else
  TAG="${TAG_INPUT}"
fi

echo "=================================================================="
echo " [PROD PIPELINE] Deploying Pre-Built Image Artifact to PROD"
echo " Image Tag: ${TAG}"
echo " Note:      Reusing existing container image (NO REBUILD)"
echo "=================================================================="

# Execute deploy.sh targeting prod environment without rebuilding
"${SCRIPT_DIR}/deploy.sh" prod "${TAG}"

echo "=================================================================="
echo " [SUCCESS] PROD Deployment Complete for tag: ${TAG}"
echo "=================================================================="
