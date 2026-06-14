#!/usr/bin/env bash
set -euo pipefail

# ───────────────────────────────────────────────────────
# RankRoute — Azure Deployment Script
# Prerequisites: az CLI logged in, GitHub repo configured
# ───────────────────────────────────────────────────────

RESOURCE_GROUP="rankroute-prod"
LOCATION="centralindia"
ACR_NAME="rankrouteacrind"  # must be globally unique, all lowercase
ACA_ENV="rankroute-env"
REDIS_NAME="rankroute-redis"
BACKEND_ACA="rankroute-api"
CADDY_ACA="rankroute-caddy"
WORKER_ACA="rankroute-worker"
BEAT_ACA="rankroute-beat"
CHROMADB_ACA="rankroute-chromadb"
STORAGE_ACCOUNT="rankroutestoreind"  # must be globally unique, lowercase
CHROMA_SHARE="chroma-data"

# ── Required Env Vars ──────────────────────────────
: "${FRONTEND_URL:?Must set FRONTEND_URL (e.g. https://app.rankroute.vocoweb.in)}"
: "${BACKEND_URL:?Must set BACKEND_URL (e.g. https://api.rankroute.vocoweb.in)}"
: "${SUPABASE_URL:?Must set SUPABASE_URL}"
: "${SUPABASE_SERVICE_KEY:?Must set SUPABASE_SERVICE_KEY}"
: "${SUPABASE_JWT_SECRET:?Must set SUPABASE_JWT_SECRET}"
: "${SUPABASE_ANON_KEY:?Must set SUPABASE_ANON_KEY}"
: "${GROQ_API_KEY:?Must set GROQ_API_KEY}"
: "${TAVILY_API_KEY:?Must set TAVILY_API_KEY}"

# ── Resource Group ──────────────────────────────────
echo "Creating resource group..."
az group create --name "$RESOURCE_GROUP" --location "$LOCATION"

# ── Azure Container Registry ────────────────────────
echo "Creating Container Registry..."
az acr create --resource-group "$RESOURCE_GROUP" --name "$ACR_NAME" --sku Basic --admin-enabled true
ACR_PASSWORD=$(az acr credential show --name "$ACR_NAME" --query "passwords[0].value" -o tsv | tr -d '\r')

# Redis will be deployed as an internal Azure Container App

# ── Identity & Key Vault ────────────────────────────
IDENTITY_NAME="rankroute-identity"
echo "Creating User-Assigned Identity..."
az identity create --name "$IDENTITY_NAME" --resource-group "$RESOURCE_GROUP" --location "$LOCATION"
IDENTITY_ID=$(az identity show --name "$IDENTITY_NAME" --resource-group "$RESOURCE_GROUP" --query "id" -o tsv | tr -d '\r')
IDENTITY_PRINCIPAL_ID=$(az identity show --name "$IDENTITY_NAME" --resource-group "$RESOURCE_GROUP" --query "principalId" -o tsv | tr -d '\r')

KV_NAME="rr-kv-rankroute-prod"
if ! az keyvault show --name "$KV_NAME" --resource-group "$RESOURCE_GROUP" > /dev/null 2>&1; then
  echo "Creating Key Vault ($KV_NAME)..."
  az keyvault create --name "$KV_NAME" --resource-group "$RESOURCE_GROUP" --location "$LOCATION" --enable-rbac-authorization false
else
  echo "Key Vault ($KV_NAME) already exists, skipping creation."
fi
az keyvault set-policy --name "$KV_NAME" --object-id "$IDENTITY_PRINCIPAL_ID" --secret-permissions get list
KV_URI="https://$KV_NAME.vault.azure.net"

echo "Storing secrets in Key Vault..."
az keyvault secret set --vault-name "$KV_NAME" --name "supabase-url" --value "${SUPABASE_URL:-}" > /dev/null
az keyvault secret set --vault-name "$KV_NAME" --name "supabase-service-key" --value "${SUPABASE_SERVICE_KEY:-}" > /dev/null
az keyvault secret set --vault-name "$KV_NAME" --name "supabase-jwt-secret" --value "${SUPABASE_JWT_SECRET:-}" > /dev/null
az keyvault secret set --vault-name "$KV_NAME" --name "supabase-anon-key" --value "${SUPABASE_ANON_KEY:-}" > /dev/null
az keyvault secret set --vault-name "$KV_NAME" --name "groq-api-key" --value "${GROQ_API_KEY:-}" > /dev/null
az keyvault secret set --vault-name "$KV_NAME" --name "tavily-api-key" --value "${TAVILY_API_KEY:-}" > /dev/null
az keyvault secret set --vault-name "$KV_NAME" --name "agent-api-keys" --value "${AGENT_API_KEYS:-NOT_SET}" > /dev/null
az keyvault secret set --vault-name "$KV_NAME" --name "huggingface-api-token" --value "${HUGGINGFACE_API_TOKEN:-NOT_SET}" > /dev/null

# Freemium & SMTP Secrets
az keyvault secret set --vault-name "$KV_NAME" --name "smtp-user" --value "${SMTP_USER:-NOT_SET}" > /dev/null
az keyvault secret set --vault-name "$KV_NAME" --name "smtp-password" --value "${SMTP_PASSWORD:-NOT_SET}" > /dev/null
az keyvault secret set --vault-name "$KV_NAME" --name "admin-alert-email" --value "${ADMIN_ALERT_EMAIL:-NOT_SET}" > /dev/null

# ── Container Apps Environment ──────────────────────
echo "Creating Container Apps Environment..."
az containerapp env create \
  --name "$ACA_ENV" \
  --resource-group "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --logs-destination none

# ── Azure Storage (for ChromaDB persistence) ────────
echo "Creating Azure Storage Account..."
az storage account create \
  --name "$STORAGE_ACCOUNT" \
  --resource-group "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --sku Standard_LRS

STORAGE_KEY=$(az storage account keys list \
  --account-name "$STORAGE_ACCOUNT" \
  --resource-group "$RESOURCE_GROUP" \
  --query "[0].value" -o tsv | tr -d '\r')

echo "Creating Azure Files Share..."
az storage share-rm create \
  --resource-group "$RESOURCE_GROUP" \
  --storage-account "$STORAGE_ACCOUNT" \
  --name "$CHROMA_SHARE" \
  --quota 5

echo "Linking storage to ACA environment..."
az containerapp env storage set \
  --name "$ACA_ENV" \
  --resource-group "$RESOURCE_GROUP" \
  --storage-name chromastorage \
  --azure-file-account-name "$STORAGE_ACCOUNT" \
  --azure-file-account-key "$STORAGE_KEY" \
  --azure-file-share-name "$CHROMA_SHARE" \
  --access-mode ReadWrite

# ── Generate ChromaDB Auth Token ────────────────────
CHROMA_TOKEN=$(openssl rand -hex 32)
echo "Storing ChromaDB auth token in Key Vault..."
az keyvault secret set --vault-name "$KV_NAME" --name "chroma-auth-token" --value "$CHROMA_TOKEN" > /dev/null

# ── Build Docker Images ─────────────────────────────
echo "Building and pushing Docker images..."
az acr build --registry "$ACR_NAME" --image rankroute-api:latest ../../backend/.
az acr build --registry "$ACR_NAME" --image rankroute-worker:latest --file ../../backend/Dockerfile --build-arg CMD="celery" ../../backend/.
az acr build --registry "$ACR_NAME" --image rankroute-caddy:latest --file ../../backend/Dockerfile.caddy ../../backend/.
az acr import --name "$ACR_NAME" --source docker.io/chromadb/chroma:latest --image rankroute-chromadb:latest --force
az acr import --name "$ACR_NAME" --source docker.io/library/redis:7.4.9-alpine --image rankroute-redis:latest --force

echo "Granting identity access to ACR..."
ACR_ID=$(az acr show --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" --query "id" -o tsv | tr -d '\r')
az role assignment create --assignee "$IDENTITY_PRINCIPAL_ID" --scope "$ACR_ID" --role AcrPull

# ── Deploy Redis Container App ──────────────────────
echo "Deploying Redis container..."
az containerapp create \
  --name "$REDIS_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --environment "$ACA_ENV" \
  --image "$ACR_NAME.azurecr.io/rankroute-redis:latest" \
  --registry-server "$ACR_NAME.azurecr.io" \
  --target-port 6379 \
  --ingress internal \
  --min-replicas 1 \
  --max-replicas 1 \
  --cpu 0.25 \
  --memory 0.5Gi \
  --user-assigned "$IDENTITY_ID" \
  --registry-identity "$IDENTITY_ID"

echo "Retrieving Redis FQDN..."
REDIS_HOST=$(az containerapp show --name "$REDIS_NAME" --resource-group "$RESOURCE_GROUP" --query "properties.configuration.ingress.fqdn" -o tsv | tr -d '\r')

echo "Storing Redis URL secret in Key Vault..."
az keyvault secret set --vault-name "$KV_NAME" --name "redis-url" --value "redis://$REDIS_HOST:6379/0" > /dev/null

# ── Deploy ChromaDB Container ───────────────────────
echo "Deploying ChromaDB container..."
az containerapp create \
  --name "$CHROMADB_ACA" \
  --resource-group "$RESOURCE_GROUP" \
  --environment "$ACA_ENV" \
  --image "$ACR_NAME.azurecr.io/rankroute-chromadb:latest" \
  --registry-server "$ACR_NAME.azurecr.io" \
  --target-port 8000 \
  --ingress internal \
  --min-replicas 1 \
  --max-replicas 1 \
  --cpu 1.0 \
  --memory 2.0Gi \
  --user-assigned "$IDENTITY_ID" \
  --registry-identity "$IDENTITY_ID" \
  --secrets \
    chroma-auth-token="keyvaultref:$KV_URI/secrets/chroma-auth-token,identityref:$IDENTITY_ID" \
  --env-vars \
    CHROMA_SERVER_AUTH_CREDENTIALS=secretref:chroma-auth-token \
    CHROMA_SERVER_AUTH_PROVIDER="chromadb.auth.token.TokenAuthServerProvider" \
    IS_PERSISTENT=TRUE \
    PERSIST_DIRECTORY=/chroma/chroma \
  --bind-storage-volume chromastorage

# ── Deploy Backend API ──────────────────────────────
echo "Deploying API container..."
az containerapp create \
  --name "$BACKEND_ACA" \
  --resource-group "$RESOURCE_GROUP" \
  --environment "$ACA_ENV" \
  --image "$ACR_NAME.azurecr.io/rankroute-api:latest" \
  --registry-server "$ACR_NAME.azurecr.io" \
  --target-port 9000 \
  --ingress internal \
  --min-replicas 1 \
  --max-replicas 3 \
  --cpu 1.0 \
  --memory 2.0Gi \
  --user-assigned "$IDENTITY_ID" \
  --registry-identity "$IDENTITY_ID" \
  --secrets \
    redis-url="keyvaultref:$KV_URI/secrets/redis-url,identityref:$IDENTITY_ID" \
    supabase-url="keyvaultref:$KV_URI/secrets/supabase-url,identityref:$IDENTITY_ID" \
    supabase-service-key="keyvaultref:$KV_URI/secrets/supabase-service-key,identityref:$IDENTITY_ID" \
    supabase-jwt-secret="keyvaultref:$KV_URI/secrets/supabase-jwt-secret,identityref:$IDENTITY_ID" \
    supabase-anon-key="keyvaultref:$KV_URI/secrets/supabase-anon-key,identityref:$IDENTITY_ID" \
    groq-api-key="keyvaultref:$KV_URI/secrets/groq-api-key,identityref:$IDENTITY_ID" \
    tavily-api-key="keyvaultref:$KV_URI/secrets/tavily-api-key,identityref:$IDENTITY_ID" \
    agent-api-keys="keyvaultref:$KV_URI/secrets/agent-api-keys,identityref:$IDENTITY_ID" \
    huggingface-api-token="keyvaultref:$KV_URI/secrets/huggingface-api-token,identityref:$IDENTITY_ID" \
    chroma-auth-token="keyvaultref:$KV_URI/secrets/chroma-auth-token,identityref:$IDENTITY_ID" \
    smtp-user="keyvaultref:$KV_URI/secrets/smtp-user,identityref:$IDENTITY_ID" \
    smtp-password="keyvaultref:$KV_URI/secrets/smtp-password,identityref:$IDENTITY_ID" \
    admin-alert-email="keyvaultref:$KV_URI/secrets/admin-alert-email,identityref:$IDENTITY_ID" \
  --env-vars \
    REDIS_URL=secretref:redis-url \
    SUPABASE_URL=secretref:supabase-url \
    SUPABASE_SERVICE_KEY=secretref:supabase-service-key \
    SUPABASE_JWT_SECRET=secretref:supabase-jwt-secret \
    SUPABASE_ANON_KEY=secretref:supabase-anon-key \
    GROQ_API_KEY=secretref:groq-api-key \
    TAVILY_API_KEY=secretref:tavily-api-key \
    HUGGINGFACE_API_TOKEN=secretref:huggingface-api-token \
    AGENT_API_KEYS=secretref:agent-api-keys \
    FRONTEND_URL="${FRONTEND_URL}" \
    BACKEND_URL="${BACKEND_URL}" \
    DEBUG=false \
    LLM_PROVIDER=groq \
    PRIMARY_MODEL=llama-3.3-70b-versatile \
    FALLBACK_MODEL_1=llama-3.1-8b-instant \
    FALLBACK_MODEL_2=llama-3.1-8b-instant \
    CORS_ORIGINS="${FRONTEND_URL}" \
    EMBEDDING_PROVIDER=huggingface \
    EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2 \
    CHROMA_HOST=rankroute-chromadb \
    CHROMA_PORT=8000 \
    CHROMA_AUTH_TOKEN=secretref:chroma-auth-token \
    SMTP_HOST="${SMTP_HOST:-smtp.gmail.com}" \
    SMTP_PORT="${SMTP_PORT:-587}" \
    SMTP_USER=secretref:smtp-user \
    SMTP_PASSWORD=secretref:smtp-password \
    ADMIN_ALERT_EMAIL=secretref:admin-alert-email \
    TAVILY_MONTHLY_QUOTA="${TAVILY_MONTHLY_QUOTA:-1000}" \
    ANON_PROMPT_LIMIT="${ANON_PROMPT_LIMIT:-3}" \
    ANON_TAVILY_LIMIT="${ANON_TAVILY_LIMIT:-1}" \
    AUTH_TAVILY_MONTHLY_LIMIT="${AUTH_TAVILY_MONTHLY_LIMIT:-5}"

# ── Deploy Caddy Gateway ────────────────────────────
echo "Deploying Caddy Gateway container..."
for i in $(seq 1 6); do
  INTERNAL_API_FQDN=$(az containerapp show --name "$BACKEND_ACA" --resource-group "$RESOURCE_GROUP" --query "properties.configuration.ingress.fqdn" -o tsv 2>/dev/null | tr -d '\r' || true)
  if [ -n "$INTERNAL_API_FQDN" ]; then break; fi
  echo "Waiting for API FQDN (attempt $i)..."
  sleep 5
done
if [ -z "$INTERNAL_API_FQDN" ]; then
  echo "FATAL: Could not resolve API container FQDN after 30 seconds" >&2
  exit 1
fi

az containerapp create \
  --name "$CADDY_ACA" \
  --resource-group "$RESOURCE_GROUP" \
  --environment "$ACA_ENV" \
  --image "$ACR_NAME.azurecr.io/rankroute-caddy:latest" \
  --registry-server "$ACR_NAME.azurecr.io" \
  --target-port 80 \
  --ingress external \
  --min-replicas 1 \
  --max-replicas 3 \
  --cpu 0.5 \
  --memory 1.0Gi \
  --user-assigned "$IDENTITY_ID" \
  --registry-identity "$IDENTITY_ID" \
  --env-vars API_UPSTREAM="http://$INTERNAL_API_FQDN"

# ── Deploy Celery Worker ────────────────────────────
echo "Deploying Worker container..."
az containerapp create \
  --name "$WORKER_ACA" \
  --resource-group "$RESOURCE_GROUP" \
  --environment "$ACA_ENV" \
  --image "$ACR_NAME.azurecr.io/rankroute-api:latest" \
  --registry-server "$ACR_NAME.azurecr.io" \
  --command "celery" "-A" "app.worker:celery_app" "worker" "--loglevel=info" "--queues=ingestion" "--concurrency=2" \
  --min-replicas 1 \
  --max-replicas 1 \
  --cpu 0.5 \
  --memory 1.0Gi \
  --user-assigned "$IDENTITY_ID" \
  --registry-identity "$IDENTITY_ID" \
  --secrets \
    redis-url="keyvaultref:$KV_URI/secrets/redis-url,identityref:$IDENTITY_ID" \
    supabase-url="keyvaultref:$KV_URI/secrets/supabase-url,identityref:$IDENTITY_ID" \
    supabase-service-key="keyvaultref:$KV_URI/secrets/supabase-service-key,identityref:$IDENTITY_ID" \
    groq-api-key="keyvaultref:$KV_URI/secrets/groq-api-key,identityref:$IDENTITY_ID" \
    tavily-api-key="keyvaultref:$KV_URI/secrets/tavily-api-key,identityref:$IDENTITY_ID" \
    huggingface-api-token="keyvaultref:$KV_URI/secrets/huggingface-api-token,identityref:$IDENTITY_ID" \
    chroma-auth-token="keyvaultref:$KV_URI/secrets/chroma-auth-token,identityref:$IDENTITY_ID" \
    smtp-user="keyvaultref:$KV_URI/secrets/smtp-user,identityref:$IDENTITY_ID" \
    smtp-password="keyvaultref:$KV_URI/secrets/smtp-password,identityref:$IDENTITY_ID" \
    admin-alert-email="keyvaultref:$KV_URI/secrets/admin-alert-email,identityref:$IDENTITY_ID" \
  --env-vars \
    REDIS_URL=secretref:redis-url \
    SUPABASE_URL=secretref:supabase-url \
    SUPABASE_SERVICE_KEY=secretref:supabase-service-key \
    GROQ_API_KEY=secretref:groq-api-key \
    TAVILY_API_KEY=secretref:tavily-api-key \
    HUGGINGFACE_API_TOKEN=secretref:huggingface-api-token \
    CHROMA_HOST=rankroute-chromadb \
    CHROMA_PORT=8000 \
    CHROMA_AUTH_TOKEN=secretref:chroma-auth-token \
    SMTP_HOST="${SMTP_HOST:-smtp.gmail.com}" \
    SMTP_PORT="${SMTP_PORT:-587}" \
    SMTP_USER=secretref:smtp-user \
    SMTP_PASSWORD=secretref:smtp-password \
    ADMIN_ALERT_EMAIL=secretref:admin-alert-email \
    TAVILY_MONTHLY_QUOTA="${TAVILY_MONTHLY_QUOTA:-1000}" \
    DEBUG=false

# ── Deploy Celery Beat ──────────────────────────────
echo "Deploying Beat container..."
az containerapp create \
  --name "$BEAT_ACA" \
  --resource-group "$RESOURCE_GROUP" \
  --environment "$ACA_ENV" \
  --image "$ACR_NAME.azurecr.io/rankroute-api:latest" \
  --registry-server "$ACR_NAME.azurecr.io" \
  --command "celery" "-A" "app.worker:celery_app" "beat" "--loglevel=info" \
  --min-replicas 1 \
  --max-replicas 1 \
  --cpu 0.25 \
  --memory 0.5Gi \
  --user-assigned "$IDENTITY_ID" \
  --registry-identity "$IDENTITY_ID" \
  --secrets \
    redis-url="keyvaultref:$KV_URI/secrets/redis-url,identityref:$IDENTITY_ID" \
    supabase-url="keyvaultref:$KV_URI/secrets/supabase-url,identityref:$IDENTITY_ID" \
    supabase-service-key="keyvaultref:$KV_URI/secrets/supabase-service-key,identityref:$IDENTITY_ID" \
    chroma-auth-token="keyvaultref:$KV_URI/secrets/chroma-auth-token,identityref:$IDENTITY_ID" \
  --env-vars \
    REDIS_URL=secretref:redis-url \
    SUPABASE_URL=secretref:supabase-url \
    SUPABASE_SERVICE_KEY=secretref:supabase-service-key \
    CHROMA_HOST=rankroute-chromadb \
    CHROMA_PORT=8000 \
    CHROMA_AUTH_TOKEN=secretref:chroma-auth-token

# Output the API URL
API_FQDN=$(az containerapp show --name "$CADDY_ACA" --resource-group "$RESOURCE_GROUP" --query "properties.configuration.ingress.fqdn" -o tsv | tr -d '\r')
echo "──────────────────────────────────────────────"
echo "✅ Deployment complete!"
echo "API URL (Caddy Gateway): https://$API_FQDN"
echo "Frontend CORS origin: ${FRONTEND_URL:-}"
echo "──────────────────────────────────────────────"
echo ""
echo "Next steps:"
echo "  1. Configure custom domain + SSL: az containerapp hostname add ..."
echo "  2. Deploy frontend to Azure Static Web Apps or Vercel"
echo "  3. Run V5__admin_logs.sql on Supabase"
