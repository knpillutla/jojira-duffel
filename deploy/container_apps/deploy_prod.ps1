# ==============================================================================
# Script 2: Deploy Pre-Built Docker Image Artifact to PROD Environment [PowerShell]
# Usage:
#   .\deploy_prod.ps1 [-Tag v1.0.0]
# ==============================================================================
param (
    [string]$Tag = ""
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

if ([string]::IsNullOrWhiteSpace($Tag)) {
    $GitSha = git rev-parse --short HEAD 2>$null
    if ($GitSha) {
        $Tag = $GitSha.Trim()
    } else {
        $Tag = "prod-" + (Get-Date -Format "yyyyMMdd-HHmmss")
    }
}

Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host " [PROD PIPELINE] Deploying Pre-Built Image Artifact to PROD (PowerShell)" -ForegroundColor Cyan
Write-Host " Image Tag: $Tag" -ForegroundColor Cyan
Write-Host " Note:      Reusing existing container image (NO REBUILD)" -ForegroundColor Cyan
Write-Host "==================================================================" -ForegroundColor Cyan

$DeployScript = Join-Path $ScriptDir "deploy.ps1"
& $DeployScript -Env prod -Tag $Tag

Write-Host "==================================================================" -ForegroundColor Green
Write-Host " [SUCCESS] PROD Deployment Complete for tag: $Tag" -ForegroundColor Green
Write-Host "==================================================================" -ForegroundColor Green
