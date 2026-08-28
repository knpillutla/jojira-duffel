# ==============================================================================
# "Build Once, Deploy Anywhere" Azure Container Apps Deployment Script [PowerShell]
# Usage:
#   .\deploy.ps1 -Env dev -Tag v1.0.0              # Deploy pre-built image v1.0.0 to dev
#   .\deploy.ps1 -Env prod -Tag v1.0.0             # Deploy exact same image v1.0.0 to prod
#   .\deploy.ps1 -Env dev -Tag v1.0.0 -Build       # Build image once, then deploy to dev
# ==============================================================================
param (
    [string]$Env = "dev",
    [string]$Tag = "",
    [switch]$Build
)

if ([string]::IsNullOrWhiteSpace($Tag)) {
    $GitSha = git rev-parse --short HEAD 2>$null
    if ($GitSha) {
        $Tag = $GitSha.Trim()
    } else {
        $Tag = "dev-" + (Get-Date -Format "yyyyMMdd-HHmmss")
    }
}

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent (Split-Path -Parent $ScriptDir)

$EnvFile = Join-Path $ScriptDir "envs\$Env.env"

if (Test-Path $EnvFile) {
    Write-Host "[+] Loading environment configuration from '$EnvFile'..." -ForegroundColor Cyan
    Get-Content $EnvFile | ForEach-Object {
        if ($_ -match '^\s*([^#=]+)\s*=\s*"?([^"#]+)"?') {
            [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim())
        }
    }
} else {
    Write-Error "Configuration file '$EnvFile' not found!"
}

$SubscriptionId = $env:AZURE_SUBSCRIPTION_ID
$ResourceGroup = $env:AZURE_RESOURCE_GROUP
$Location = if ($env:AZURE_LOCATION) { $env:AZURE_LOCATION } else { "eastus" }
$ContainerAppEnv = $env:AZURE_CONTAINER_APP_ENV
$AcrName = $env:AZURE_ACR_NAME
$AkvName = $env:AZURE_KEYVAULT_NAME

$ApiAppName = $env:CONTAINER_APP_API_NAME
$UserSvcAppName = $env:CONTAINER_APP_USER_SERVICE_NAME
$OrderSvcAppName = $env:CONTAINER_APP_ORDER_SERVICE_NAME

$AcrServer = "$AcrName.azurecr.io"

Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host " Starting Azure Container Apps Deployment (Build Once, Deploy Anywhere)" -ForegroundColor Cyan
Write-Host " Target Environment: $Env" -ForegroundColor Cyan
Write-Host " Image Tag:          $Tag" -ForegroundColor Cyan
Write-Host " ACR Server:         $AcrServer" -ForegroundColor Cyan
Write-Host " Key Vault (AKV):    $AkvName" -ForegroundColor Cyan
Write-Host "==================================================================" -ForegroundColor Cyan

# 1. Authenticate with Azure
Write-Host "[1/5] Authenticating with Azure CLI..." -ForegroundColor Yellow
if ($SubscriptionId) { az account set --subscription $SubscriptionId }
az extension add --name containerapp --upgrade --yes

# 2. Build Stage (Only if -Build parameter is specified)
if ($Build) {
    Write-Host "[2/5] [-Build parameter set] Building Docker images ONCE and pushing to ACR..." -ForegroundColor Yellow
    az acr login --name $AcrName

    docker build -t "$AcrServer/jojira-api:$Tag" -f "$RootDir\Dockerfile" "$RootDir"
    docker push "$AcrServer/jojira-api:$Tag"

    docker build -t "$AcrServer/jojira-user-service:$Tag" -f "$RootDir\Dockerfile" "$RootDir"
    docker push "$AcrServer/jojira-user-service:$Tag"

    docker build -t "$AcrServer/jojira-order-service:$Tag" -f "$RootDir\Dockerfile.order-service" "$RootDir"
    docker push "$AcrServer/jojira-order-service:$Tag"
} else {
    Write-Host "[2/5] Skipping build step. Reusing pre-built image artifact '$Tag'..." -ForegroundColor Yellow
}

# 3. Ensure Environment Exists
Write-Host "[3/5] Ensuring Resource Group & Container Apps Environment in '$Env'..." -ForegroundColor Yellow
az group create --name $ResourceGroup --location $Location -o table

$EnvCheck = az containerapp env show --name $ContainerAppEnv --resource-group $ResourceGroup 2>$null
if (-not $EnvCheck) {
    az containerapp env create --name $ContainerAppEnv --resource-group $ResourceGroup --location $Location
}

$AcrPassword = az acr credential show --name $AcrName --query "passwords[0].value" -o tsv 2>$null

# 4. Deploy Main API Container App (Injecting Environment Configs & Secret Vault)
Write-Host "[4/5] Deploying '$ApiAppName' with environment configs from '$Env.env'..." -ForegroundColor Yellow
az containerapp create `
  --name $ApiAppName `
  --resource-group $ResourceGroup `
  --environment $ContainerAppEnv `
  --image "$AcrServer/jojira-api:$Tag" `
  --registry-server $AcrServer `
  --registry-username $AcrName `
  --registry-password $AcrPassword `
  --target-port 8000 `
  --ingress external `
  --cpu 0.5 `
  --memory 1.0Gi `
  --env-vars `
    ENVIRONMENT="$Env" `
    AZURE_KEYVAULT_ENABLED="true" `
    AZURE_KEYVAULT_NAME="$AkvName" `
    AZURE_KEYVAULT_URL="https://$AkvName.vault.azure.net/" `
    DEFAULT_ORDER_MODE="hold" `
    LLM_PROVIDER="openai" `
  --system-assigned

# 5. Deploy User Service & Order Service
Write-Host "[5/5] Deploying User Service & Order Service Container Apps..." -ForegroundColor Yellow
az containerapp create `
  --name $UserSvcAppName `
  --resource-group $ResourceGroup `
  --environment $ContainerAppEnv `
  --image "$AcrServer/jojira-user-service:$Tag" `
  --registry-server $AcrServer `
  --registry-username $AcrName `
  --registry-password $AcrPassword `
  --target-port 8001 `
  --ingress external `
  --cpu 0.25 `
  --memory 0.5Gi `
  --env-vars `
    ENVIRONMENT="$Env" `
    AZURE_KEYVAULT_ENABLED="true" `
    AZURE_KEYVAULT_NAME="$AkvName" `
    AZURE_KEYVAULT_URL="https://$AkvName.vault.azure.net/" `
  --system-assigned

az containerapp create `
  --name $OrderSvcAppName `
  --resource-group $ResourceGroup `
  --environment $ContainerAppEnv `
  --image "$AcrServer/jojira-order-service:$Tag" `
  --registry-server $AcrServer `
  --registry-username $AcrName `
  --registry-password $AcrPassword `
  --ingress disabled `
  --cpu 0.25 `
  --memory 0.5Gi `
  --env-vars `
    ENVIRONMENT="$Env" `
    AZURE_KEYVAULT_ENABLED="true" `
    AZURE_KEYVAULT_NAME="$AkvName" `
    AZURE_KEYVAULT_URL="https://$AkvName.vault.azure.net/" `
  --system-assigned

$ApiUrl = az containerapp show --name $ApiAppName --resource-group $ResourceGroup --query "properties.configuration.ingress.fqdn" -o tsv

Write-Host "==================================================================" -ForegroundColor Green
Write-Host " [SUCCESS] Deployed image '$Tag' to '$Env' environment!" -ForegroundColor Green
Write-Host " Main REST API URL: https://$ApiUrl" -ForegroundColor Green
Write-Host "==================================================================" -ForegroundColor Green
