# ==============================================================================
# Azure Key Vault Secret Seeding & Update Script (PowerShell)
# Usage: .\set_keyvault_secrets.ps1 -Env dev (or -Env prod)
# ==============================================================================

param(
    [string]$Env = "dev",
    [string]$DuffelToken = "",
    [string]$OpenAiKey = "",
    [string]$GeminiKey = "",
    [string]$PostgresPassword = "",
    [string]$ServiceBusConnString = ""
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$EnvFile = Join-Path $ScriptDir "envs\$Env.env"

if (Test-Path $EnvFile) {
    Get-Content $EnvFile | ForEach-Object {
        if ($_ -match '^\s*([^#=]+)\s*=\s*"?([^"#]+)"?') {
            [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim())
        }
    }
} else {
    Write-Error "Config file '$EnvFile' not found!"
    exit 1
}

$AkvName = $env:AZURE_KEYVAULT_NAME
$Subscription = if ($env:AZURE_SUBSCRIPTION_NAME) { $env:AZURE_SUBSCRIPTION_NAME } else { $env:AZURE_SUBSCRIPTION_ID }

if ($Subscription) { az account set --subscription $Subscription }

Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host " Setting Azure Key Vault SECRETS for Vault: '$AkvName' ($Env)" -ForegroundColor Cyan
Write-Host " Note: All sensitive values MUST be stored as SECRETS (not Keys)" -ForegroundColor Yellow
Write-Host "==================================================================" -ForegroundColor Cyan

function Set-AkvSecret {
    param([string]$SecretName, [string]$SecretValue)
    if ($SecretValue) {
        Write-Host "  -> Setting Secret: '$SecretName'..." -ForegroundColor Green
        az keyvault secret set --vault-name $AkvName --name $SecretName --value $SecretValue -o table
    } else {
        Write-Host "  [SKIP] Secret '$SecretName' value not provided." -ForegroundColor Gray
    }
}

Set-AkvSecret -SecretName "duffel-api-token" -SecretValue $DuffelToken
Set-AkvSecret -SecretName "openai-api-key" -SecretValue $OpenAiKey
Set-AkvSecret -SecretName "gemini-api-key" -SecretValue $GeminiKey
Set-AkvSecret -SecretName "postgres-password" -SecretValue $PostgresPassword
Set-AkvSecret -SecretName "service-bus-connection-string" -SecretValue $ServiceBusConnString

Write-Host "==================================================================" -ForegroundColor Green
Write-Host " [SUCCESS] Key Vault Secrets updated successfully in '$AkvName'" -ForegroundColor Green
Write-Host "==================================================================" -ForegroundColor Green
