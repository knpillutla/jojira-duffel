# ==============================================================================
# Script 1: Build Docker Images & Deploy to DEV Environment [PowerShell]
# Usage:
#   .\build_and_deploy_dev.ps1 [-Tag v1.0.0]
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
        $Tag = "dev-" + (Get-Date -Format "yyyyMMdd-HHmmss")
    }
}

Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host " [DEV PIPELINE] Building Docker Images & Deploying to DEV (PowerShell)" -ForegroundColor Cyan
Write-Host " Image Tag: $Tag" -ForegroundColor Cyan
Write-Host "==================================================================" -ForegroundColor Cyan

$DeployScript = Join-Path $ScriptDir "deploy.ps1"
& $DeployScript -Env dev -Tag $Tag -Build

Write-Host "==================================================================" -ForegroundColor Green
Write-Host " [SUCCESS] DEV Deployment Complete for tag: $Tag" -ForegroundColor Green
Write-Host "==================================================================" -ForegroundColor Green
