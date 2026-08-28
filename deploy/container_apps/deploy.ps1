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

$Subscription = if ($env:AZURE_SUBSCRIPTION_NAME) { $env:AZURE_SUBSCRIPTION_NAME } elseif ($env:AZURE_SUBSCRIPTION_ID) { $env:AZURE_SUBSCRIPTION_ID } else { $env:AZURE_SUBSCRIPTION }
$ResourceGroup = $env:AZURE_RESOURCE_GROUP
$Location = if ($env:AZURE_LOCATION) { $env:AZURE_LOCATION } else { "eastus" }
$ContainerAppEnv = $env:AZURE_CONTAINER_APP_ENV
$AcrName = $env:AZURE_ACR_NAME
$AkvName = $env:AZURE_KEYVAULT_NAME

$ApiAppName = $env:CONTAINER_APP_API_NAME
$UserSvcAppName = $env:CONTAINER_APP_USER_SERVICE_NAME
$OrderSvcAppName = $env:CONTAINER_APP_ORDER_SERVICE_NAME
$PostgresAppName = if ($env:CONTAINER_APP_POSTGRES_NAME) { $env:CONTAINER_APP_POSTGRES_NAME } else { "app-jojira-postgres-$Env" }
$RedisAppName = if ($env:CONTAINER_APP_REDIS_NAME) { $env:CONTAINER_APP_REDIS_NAME } else { "app-jojira-redis-$Env" }
$RabbitMqAppName = if ($env:CONTAINER_APP_RABBITMQ_NAME) { $env:CONTAINER_APP_RABBITMQ_NAME } else { "app-jojira-rabbitmq-$Env" }

$AcrServer = "$AcrName.azurecr.io"

Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host " Starting Azure Container Apps Deployment (Build Once, Deploy Anywhere)" -ForegroundColor Cyan
Write-Host " Target Environment: $Env" -ForegroundColor Cyan
Write-Host " Subscription:       $Subscription" -ForegroundColor Cyan
Write-Host " Image Tag:          $Tag" -ForegroundColor Cyan
Write-Host " ACR Server:         $AcrServer" -ForegroundColor Cyan
Write-Host " Key Vault (AKV):    $AkvName" -ForegroundColor Cyan
Write-Host "==================================================================" -ForegroundColor Cyan

# 1. Authenticate with Azure
Write-Host "[1/6] Authenticating with Azure CLI..." -ForegroundColor Yellow
if ($Subscription) { az account set --subscription $Subscription }
az extension add --name containerapp --upgrade --yes --allow-preview true

# 2. Build & Push Stage (Only if -Build parameter is specified)
if ($Build) {
    Write-Host "[2/6] [-Build parameter set] Building & Pushing Docker images for Services + Infra..." -ForegroundColor Yellow
    az acr login --name $AcrName

    Write-Host "      [1/6] Building Booking API image ($AcrServer/jojira-api:$Tag)..." -ForegroundColor Yellow
    docker build -t "$AcrServer/jojira-api:$Tag" -f "$RootDir\Dockerfile.booking-service" "$RootDir"
    docker push "$AcrServer/jojira-api:$Tag"

    Write-Host "      [2/6] Building User Service image ($AcrServer/jojira-user-service:$Tag)..." -ForegroundColor Yellow
    docker build -t "$AcrServer/jojira-user-service:$Tag" -f "$RootDir\Dockerfile.user-service" "$RootDir"
    docker push "$AcrServer/jojira-user-service:$Tag"

    Write-Host "      [3/6] Building Order Service image ($AcrServer/jojira-order-service:$Tag)..." -ForegroundColor Yellow
    docker build -t "$AcrServer/jojira-order-service:$Tag" -f "$RootDir\Dockerfile.order-service" "$RootDir"
    docker push "$AcrServer/jojira-order-service:$Tag"

    Write-Host "      [4/6] Pulling & Pushing PostgreSQL image ($AcrServer/postgres:$Tag)..." -ForegroundColor Yellow
    docker pull postgres:16-alpine
    docker tag postgres:16-alpine "$AcrServer/postgres:$Tag"
    docker push "$AcrServer/postgres:$Tag"

    Write-Host "      [5/6] Pulling & Pushing Redis image ($AcrServer/redis:$Tag)..." -ForegroundColor Yellow
    docker pull redis:7-alpine
    docker tag redis:7-alpine "$AcrServer/redis:$Tag"
    docker push "$AcrServer/redis:$Tag"

    Write-Host "      [6/6] Pulling & Pushing RabbitMQ image ($AcrServer/rabbitmq:$Tag)..." -ForegroundColor Yellow
    docker pull rabbitmq:3-management-alpine
    docker tag rabbitmq:3-management-alpine "$AcrServer/rabbitmq:$Tag"
    docker push "$AcrServer/rabbitmq:$Tag"
} else {
    Write-Host "[2/6] Skipping build step. Reusing pre-built image artifacts..." -ForegroundColor Yellow
}

# 3. Ensure Environment Exists
Write-Host "[3/6] Ensuring Resource Group & Container Apps Environment in '$Env'..." -ForegroundColor Yellow
az group create --name $ResourceGroup --location $Location -o table

$PrevEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$EnvCheck = az containerapp env show --name $ContainerAppEnv --resource-group $ResourceGroup 2>$null
if (-not $EnvCheck) {
    az containerapp env create --name $ContainerAppEnv --resource-group $ResourceGroup --location $Location
}
az acr update --name $AcrName --admin-enabled true
$AcrPasswordRaw = az acr credential show --name $AcrName --query "passwords[0].value" -o tsv
$AcrPassword = if ($AcrPasswordRaw) { $AcrPasswordRaw.Trim() } else { "" }
$ErrorActionPreference = $PrevEap

if ([string]::IsNullOrWhiteSpace($AcrPassword)) {
    Write-Error "Failed to fetch ACR password for '$AcrName'. Ensure Azure CLI is authenticated."
}

$Cpu = if ($env:CPU) { $env:CPU } else { "0.25" }
$Memory = if ($env:MEMORY) { $env:MEMORY } else { "0.5Gi" }
$MinReplicas = if ($env:MIN_REPLICAS) { $env:MIN_REPLICAS } else { "0" }
$MaxReplicas = if ($env:MAX_REPLICAS) { $env:MAX_REPLICAS } else { "10" }

# 4. Deploy Infrastructure Containers (PostgreSQL, Redis, RabbitMQ)
Write-Host "[4/6] Deploying PostgreSQL, Redis, and RabbitMQ Container Apps..." -ForegroundColor Yellow

az containerapp create `
  --name $PostgresAppName `
  --resource-group $ResourceGroup `
  --environment $ContainerAppEnv `
  --image "$AcrServer/postgres:$Tag" `
  --registry-server $AcrServer `
  --registry-username $AcrName `
  --registry-password $AcrPassword `
  --target-port 5432 `
  --ingress internal `
  --cpu $Cpu `
  --memory $Memory `
  --min-replicas 1 `
  --max-replicas 1 `
  --env-vars `
    POSTGRES_DB="jojira_duffel" `
    POSTGRES_USER="postgres" `
    POSTGRES_PASSWORD="postgres"

az containerapp create `
  --name $RedisAppName `
  --resource-group $ResourceGroup `
  --environment $ContainerAppEnv `
  --image "$AcrServer/redis:$Tag" `
  --registry-server $AcrServer `
  --registry-username $AcrName `
  --registry-password $AcrPassword `
  --target-port 6379 `
  --ingress internal `
  --cpu $Cpu `
  --memory $Memory `
  --min-replicas 1 `
  --max-replicas 1

az containerapp create `
  --name $RabbitMqAppName `
  --resource-group $ResourceGroup `
  --environment $ContainerAppEnv `
  --image "$AcrServer/rabbitmq:$Tag" `
  --registry-server $AcrServer `
  --registry-username $AcrName `
  --registry-password $AcrPassword `
  --target-port 5672 `
  --ingress internal `
  --cpu $Cpu `
  --memory $Memory `
  --min-replicas 1 `
  --max-replicas 1

# 5. Deploy Main API Container App
Write-Host "[5/6] Deploying '$ApiAppName' with environment configs from '$Env.env'..." -ForegroundColor Yellow
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
  --cpu $Cpu `
  --memory $Memory `
  --min-replicas $MinReplicas `
  --max-replicas $MaxReplicas `
  --env-vars `
    ENVIRONMENT="$Env" `
    AZURE_KEYVAULT_ENABLED="true" `
    AZURE_KEYVAULT_NAME="$AkvName" `
    AZURE_KEYVAULT_URL="https://$AkvName.vault.azure.net/" `
    DEFAULT_ORDER_MODE="instant" `
    LLM_PROVIDER="openai" `
    POSTGRES_HOST="$PostgresAppName" `
    POSTGRES_PORT="5432" `
    POSTGRES_DB="jojira_duffel" `
    POSTGRES_USER="postgres" `
    POSTGRES_PASSWORD="postgres" `
    REDIS_HOST="$RedisAppName" `
    REDIS_PORT="6379" `
    RABBITMQ_HOST="$RabbitMqAppName" `
    RABBITMQ_PORT="5672" `
  --system-assigned

# 6. Deploy User Service & Order Service
Write-Host "[6/6] Deploying User Service & Order Service Container Apps..." -ForegroundColor Yellow
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
  --cpu $Cpu `
  --memory $Memory `
  --min-replicas $MinReplicas `
  --max-replicas $MaxReplicas `
  --env-vars `
    ENVIRONMENT="$Env" `
    AZURE_KEYVAULT_ENABLED="true" `
    AZURE_KEYVAULT_NAME="$AkvName" `
    AZURE_KEYVAULT_URL="https://$AkvName.vault.azure.net/" `
    POSTGRES_HOST="$PostgresAppName" `
    POSTGRES_PORT="5432" `
    POSTGRES_DB="jojira_duffel" `
    POSTGRES_USER="postgres" `
    POSTGRES_PASSWORD="postgres" `
  --system-assigned

az containerapp create `
  --name $OrderSvcAppName `
  --resource-group $ResourceGroup `
  --environment $ContainerAppEnv `
  --image "$AcrServer/jojira-order-service:$Tag" `
  --registry-server $AcrServer `
  --registry-username $AcrName `
  --registry-password $AcrPassword `
  --cpu $Cpu `
  --memory $Memory `
  --min-replicas $MinReplicas `
  --max-replicas $MaxReplicas `
  --env-vars `
    ENVIRONMENT="$Env" `
    AZURE_KEYVAULT_ENABLED="true" `
    AZURE_KEYVAULT_NAME="$AkvName" `
    AZURE_KEYVAULT_URL="https://$AkvName.vault.azure.net/" `
    POSTGRES_HOST="$PostgresAppName" `
    POSTGRES_PORT="5432" `
    POSTGRES_DB="jojira_duffel" `
    POSTGRES_USER="postgres" `
    POSTGRES_PASSWORD="postgres" `
    REDIS_HOST="$RedisAppName" `
    REDIS_PORT="6379" `
    RABBITMQ_HOST="$RabbitMqAppName" `
    RABBITMQ_PORT="5672" `
  --system-assigned

$ApiUrl = az containerapp show --name $ApiAppName --resource-group $ResourceGroup --query "properties.configuration.ingress.fqdn" -o tsv

Write-Host "==================================================================" -ForegroundColor Green
Write-Host " [SUCCESS] Deployed image '$Tag' to '$Env' environment!" -ForegroundColor Green
Write-Host " Main REST API URL: https://$ApiUrl" -ForegroundColor Green
Write-Host " Infrastructure Deployed: Postgres ($PostgresAppName), Redis ($RedisAppName), RabbitMQ ($RabbitMqAppName)" -ForegroundColor Green
Write-Host "==================================================================" -ForegroundColor Green
