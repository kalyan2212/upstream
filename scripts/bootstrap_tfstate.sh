#!/bin/bash
# =============================================================================
# bootstrap_tfstate.sh
# Run this ONCE manually (from your local machine or Azure Cloud Shell)
# BEFORE the first `terraform init`.
#
# Creates the Azure Storage Account that stores Terraform remote state.
#
# Usage:
#   az login
#   bash scripts/bootstrap_tfstate.sh
# =============================================================================
set -euo pipefail

LOCATION="eastus"
RG="rg-tfstate-upstream"
SA="sttfstateupstream001"   # must be globally unique, lowercase, 3-24 chars
CONTAINER="tfstate"

echo "==> Creating resource group: $RG"
az group create --name "$RG" --location "$LOCATION" --output none

echo "==> Creating storage account: $SA"
az storage account create \
  --name "$SA" \
  --resource-group "$RG" \
  --location "$LOCATION" \
  --sku Standard_LRS \
  --kind StorageV2 \
  --allow-blob-public-access false \
  --min-tls-version TLS1_2 \
  --output none

echo "==> Creating blob container: $CONTAINER"
az storage container create \
  --name "$CONTAINER" \
  --account-name "$SA" \
  --auth-mode login \
  --output none

echo ""
echo "✅ Terraform state backend ready."
echo "   Resource Group : $RG"
echo "   Storage Account: $SA"
echo "   Container      : $CONTAINER"
echo ""
echo "Next step: Run 'terraform init' inside the terraform/ directory."
