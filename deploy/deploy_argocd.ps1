# ==============================================================================
# Connect to Azure AKS & Deploy ArgoCD Application [PowerShell]
# ==============================================================================
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ConfigFile = Join-Path $ScriptDir "config.env"

if (Test-Path $ConfigFile) {
    Get-Content $ConfigFile | ForEach-Object {
        if ($_ -match '^\s*([^#=]+)\s*=\s*"?([^"#]+)"?') {
            [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim())
        }
    }
}

$ResourceGroup = $env:AZURE_RESOURCE_GROUP
$AksCluster = $env:AZURE_AKS_CLUSTER
$K8sNamespace = if ($env:K8S_NAMESPACE) { $env:K8S_NAMESPACE } else { "jojira" }
$AppName = if ($env:ARGOCD_APP_NAME) { $env:ARGOCD_APP_NAME } else { "jojira-duffel-app" }

Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host " Connecting to Azure AKS & Registering ArgoCD App (PowerShell)" -ForegroundColor Cyan
Write-Host " Resource Group: $ResourceGroup" -ForegroundColor Cyan
Write-Host " AKS Cluster:    $AksCluster" -ForegroundColor Cyan
Write-Host " ArgoCD App:     $AppName" -ForegroundColor Cyan
Write-Host "==================================================================" -ForegroundColor Cyan

# 1. Fetch AKS credentials
Write-Host "[1/3] Fetching AKS Credentials..." -ForegroundColor Yellow
az aks get-credentials --resource-group $ResourceGroup --name $AksCluster --overwrite-existing

# 2. Prepare namespace
Write-Host "[2/3] Preparing Kubernetes namespace '$K8sNamespace'..." -ForegroundColor Yellow
kubectl create namespace $K8sNamespace --dry-run=client -o yaml | kubectl apply -f -

# 3. Apply ArgoCD application manifest
Write-Host "[3/3] Registering Application in ArgoCD..." -ForegroundColor Yellow
$AppManifest = Join-Path $ScriptDir "argocd\application.yaml"
kubectl apply -f $AppManifest

Write-Host "==================================================================" -ForegroundColor Green
Write-Host " [SUCCESS] ArgoCD Application registered successfully!" -ForegroundColor Green
Write-Host "==================================================================" -ForegroundColor Green
