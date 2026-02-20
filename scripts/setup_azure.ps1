#!/usr/bin/env pwsh
# =============================================================================
# setup_azure.ps1
# Fully automated: SP creation, SSH key gen, Terraform state bootstrap,
# and GitHub secrets upload — all in one run.
#
# Run AFTER az login:
#   powershell -ExecutionPolicy Bypass -File scripts/setup_azure.ps1
# =============================================================================

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function az { & "C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd" @args }

# ── Colour helpers ────────────────────────────────────────────────────────────
function Info  { param($m) Write-Host "[INFO]  $m" -ForegroundColor Cyan }
function Ok    { param($m) Write-Host "[OK]    $m" -ForegroundColor Green }
function Err   { param($m) Write-Host "[ERROR] $m" -ForegroundColor Red; exit 1 }
function Step  { param($m) Write-Host "`n===== $m =====" -ForegroundColor Yellow }

# ── Config ────────────────────────────────────────────────────────────────────
$GITHUB_OWNER  = "kalyan2212"
$GITHUB_REPO   = "upstream"
$SP_NAME       = "sp-upstream-deploy"
$SSH_KEY_PATH  = "$env:USERPROFILE\.ssh\upstream_deploy_key"
$TF_RG         = "rg-tfstate-upstream"
$TF_SA         = "sttfstateupstream001"
$TF_CONTAINER  = "tfstate"
$LOCATION      = "eastus"

# ═════════════════════════════════════════════════════════════════════════════
Step "1 / 5 — Verifying Azure login"
# ═════════════════════════════════════════════════════════════════════════════
try {
    $account = az account show -o json | ConvertFrom-Json
} catch {
    Err "Not logged in. Please run: az login --use-device-code"
}
$SUB_ID   = $account.id
$TENANT_ID = $account.tenantId
Ok "Logged in as: $($account.user.name)"
Ok "Subscription : $($account.name) ($SUB_ID)"

# ═════════════════════════════════════════════════════════════════════════════
Step "2 / 5 — Creating Service Principal"
# ═════════════════════════════════════════════════════════════════════════════
Info "Creating SP: $SP_NAME ..."
$spJson = az ad sp create-for-rbac `
    --name $SP_NAME `
    --role Contributor `
    --scopes "/subscriptions/$SUB_ID" `
    -o json | ConvertFrom-Json

$CLIENT_ID     = $spJson.appId
$CLIENT_SECRET = $spJson.password
Ok "Service Principal created: $CLIENT_ID"

# ═════════════════════════════════════════════════════════════════════════════
Step "3 / 5 — Generating SSH Key Pair"
# ═════════════════════════════════════════════════════════════════════════════
if (-not (Test-Path "$SSH_KEY_PATH")) {
    Info "Generating 4096-bit RSA key at $SSH_KEY_PATH ..."
    New-Item -ItemType Directory -Force -Path (Split-Path $SSH_KEY_PATH) | Out-Null
    ssh-keygen -t rsa -b 4096 -f $SSH_KEY_PATH -N '""' -q
    Ok "SSH key pair generated."
} else {
    Ok "SSH key already exists at $SSH_KEY_PATH — reusing."
}
$SSH_PUB_KEY  = Get-Content "$SSH_KEY_PATH.pub" -Raw
$SSH_PRIV_KEY = Get-Content $SSH_KEY_PATH -Raw

# ═════════════════════════════════════════════════════════════════════════════
Step "4 / 5 — Bootstrapping Terraform State Storage"
# ═════════════════════════════════════════════════════════════════════════════
Info "Creating resource group: $TF_RG ..."
az group create --name $TF_RG --location $LOCATION -o none
Ok "Resource group ready."

Info "Creating storage account: $TF_SA ..."
az storage account create `
    --name $TF_SA `
    --resource-group $TF_RG `
    --location $LOCATION `
    --sku Standard_LRS `
    --kind StorageV2 `
    --allow-blob-public-access false `
    --min-tls-version TLS1_2 `
    -o none
Ok "Storage account ready."

Info "Creating blob container: $TF_CONTAINER ..."
az storage container create `
    --name $TF_CONTAINER `
    --account-name $TF_SA `
    --auth-mode login `
    -o none
Ok "Blob container ready. Terraform state backend is set up."

# ═════════════════════════════════════════════════════════════════════════════
Step "5 / 5 — Uploading GitHub Actions Secrets"
# ═════════════════════════════════════════════════════════════════════════════
Info "Setting GitHub secrets via gh CLI ..."

# Check gh is available
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Info "GitHub CLI (gh) not found — installing via winget..."
    winget install --id GitHub.cli --silent --accept-source-agreements --accept-package-agreements
    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("PATH","User")
}

$repo = "$GITHUB_OWNER/$GITHUB_REPO"

$secrets = @{
    "AZURE_CLIENT_ID"       = $CLIENT_ID
    "AZURE_CLIENT_SECRET"   = $CLIENT_SECRET
    "AZURE_SUBSCRIPTION_ID" = $SUB_ID
    "AZURE_TENANT_ID"       = $TENANT_ID
    "SSH_PUBLIC_KEY"        = $SSH_PUB_KEY.Trim()
    "SSH_PRIVATE_KEY"       = $SSH_PRIV_KEY.Trim()
}

foreach ($name in $secrets.Keys) {
    $value = $secrets[$name]
    $value | gh secret set $name --repo $repo
    Ok "Secret set: $name"
}

# ═════════════════════════════════════════════════════════════════════════════
Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║  ALL DONE!  All 6 secrets are live in GitHub.           ║" -ForegroundColor Green
Write-Host "║                                                          ║" -ForegroundColor Green
Write-Host "║  Trigger deployment:                                     ║" -ForegroundColor Green
Write-Host "║  https://github.com/$GITHUB_OWNER/$GITHUB_REPO/actions  ║" -ForegroundColor Green
Write-Host "║                                                          ║" -ForegroundColor Green
Write-Host "║  Or push any change to main branch to auto-deploy.      ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════════════════════╝" -ForegroundColor Green
