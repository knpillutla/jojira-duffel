# ==============================================================================
# Build Docker Images & Push to Azure Container Registry (ACR) [PowerShell]
# ==============================================================================
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent $ScriptDir
$ConfigFile = Join-Path $ScriptDir "config.env"

if (Test-Path $ConfigFile) {
    Get-Content $ConfigFile | ForEach-Object {
        if ($_ -match '^\s*([^#=]+)\s*=\s*"?([^"#]+)"?') {
            [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim())
        }
    }
} else {
    Write-Error "Configuration file '$ConfigFile' not found!"
}

$AcrName = $env:AZURE_ACR_NAME
$SubscriptionId = $env:AZURE_SUBSCRIPTION_ID
$Tag = if ($env:IMAGE_TAG) { $env:IMAGE_TAG } else { "latest" }
$AcrLoginServer = "$AcrName.azurecr.io"

Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host " Starting Build & Push to Azure Container Registry (PowerShell)" -ForegroundColor Cyan
Write-Host " ACR Name: $AcrName ($AcrLoginServer)" -ForegroundColor Cyan
Write-Host " Image Tag: $Tag" -ForegroundColor Cyan
Write-Host "==================================================================" -ForegroundColor Cyan

# 1. Login to Azure & ACR
Write-Host "[1/4] Authenticating with Azure ACR..." -ForegroundColor Yellow
if ($SubscriptionId) { az account set --subscription $SubscriptionId }
az acr login --name $AcrName

# 2. Build & Push API Image
Write-Host "[2/4] Building & Pushing jojira-api image..." -ForegroundColor Yellow
docker build -t "$AcrLoginServer/jojira-api:$Tag" -t "$AcrLoginServer/jojira-api:latest" -f "$RootDir\Dockerfile" "$RootDir"
docker push "$AcrLoginServer/jojira-api:$Tag"
docker push "$AcrLoginServer/jojira-api:latest"

# 3. Build & Push User Service Image
Write-Host "[3/4] Building & Pushing jojira-user-service image..." -ForegroundColor Yellow
docker build -t "$AcrLoginServer/jojira-user-service:$Tag" -t "$AcrLoginServer/jojira-user-service:latest" -f "$RootDir\Dockerfile" "$RootDir"
docker push "$AcrLoginServer/jojira-user-service:$Tag"
docker push "$AcrLoginServer/jojira-user-service:latest"

# 4. Build & Push Order Service Image
Write-Host "[4/4] Building & Pushing jojira-order-service image..." -ForegroundColor Yellow
docker build -t "$AcrLoginServer/jojira-order-service:$Tag" -t "$AcrLoginServer/jojira-order-service:latest" -f "$RootDir\Dockerfile.order-service" "$RootDir"
docker push "$AcrLoginServer/jojira-order-service:$Tag"
docker push "$AcrLoginServer/jojira-order-service:latest"

Write-Host "==================================================================" -ForegroundColor Green
Write-Host " [SUCCESS] Images successfully built & pushed to $AcrLoginServer!" -ForegroundColor Green
Write-Host "==================================================================" -ForegroundColor Green
