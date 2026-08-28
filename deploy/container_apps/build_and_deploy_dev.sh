#!/usr/bin/env bash
# ==============================================================================
# Script 1: Build Docker Images & Deploy to DEV Environment
# Usage:
#   ./build_and_deploy_dev.sh [image_tag]
# Example:
#   ./build_and_deploy_dev.sh v1.0.0
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TAG_INPUT="${1:-}"

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

echo "=================================================================="
echo " [DEV PIPELINE] Building Docker Images & Deploying to DEV"
echo " Image Tag: ${TAG}"
echo "=================================================================="

# Execute deploy.sh targeting dev environment with --build flag enabled
"${SCRIPT_DIR}/deploy.sh" dev "${TAG}" --build

echo "=================================================================="
echo " [SUCCESS] DEV Deployment Complete for tag: ${TAG}"
echo "=================================================================="
