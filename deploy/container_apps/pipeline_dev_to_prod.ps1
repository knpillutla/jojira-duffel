# ==============================================================================
# Script 3: Full Release Pipeline (Build Once -> Deploy DEV -> Deploy PROD) [PowerShell]
# Usage:
#   .\pipeline_dev_to_prod.ps1 [-Tag v1.0.0]
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
        $Tag = "release-" + (Get-Date -Format "yyyyMMdd-HHmmss")
    }
}

Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host " Starting Full End-to-End Release Pipeline (Build -> DEV -> PROD)" -ForegroundColor Cyan
Write-Host " Image Release Tag: $Tag" -ForegroundColor Cyan
Write-Host "==================================================================" -ForegroundColor Cyan

# Stage 1: Build & Deploy to DEV
Write-Host "[STAGE 1/2] Building image once & deploying to DEV..." -ForegroundColor Yellow
$DevScript = Join-Path $ScriptDir "build_and_deploy_dev.ps1"
& $DevScript -Tag $Tag

# Stage 2: Deploy to PROD
Write-Host "[STAGE 2/2] Promoting pre-built image '$Tag' to PROD..." -ForegroundColor Yellow
$ProdScript = Join-Path $ScriptDir "deploy_prod.ps1"
& $ProdScript -Tag $Tag

Write-Host "==================================================================" -ForegroundColor Green
Write-Host " [FULL PIPELINE SUCCESS] Release '$Tag' successfully deployed to DEV & PROD!" -ForegroundColor Green
Write-Host "==================================================================" -ForegroundColor Green
