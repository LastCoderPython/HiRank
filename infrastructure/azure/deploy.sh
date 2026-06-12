#!/usr/bin/env bash
set -euo pipefail

# ───────────────────────────────────────────────────────
# RankRoute — Azure Deployment Script
# Prerequisites: az CLI logged in, GitHub repo configured
# ───────────────────────────────────────────────────────

RESOURCE_GROUP="rankroute-prod"
LOCATION="eastus"
ACR_NAME="rankrouteacr"  # must be globally unique, all lowercase
ACA_ENV="rankroute-env"
REDIS_NAME="rankroute-redis"
BACKEND_ACA="rankroute-api"
WORKER_ACA="rankroute-worker"
BEAT_ACA="rankroute-beat"
CHROMADB_ACA="rankroute-chromadb"
STORAGE_ACCOUNT="rankroutestorage"  # must be globally unique, lowercase
CHROMA_SHARE="chroma-data"

# ── Resource Group ──────────────────────────────────
echo "Creating resource group..."
az group create --name "$RESOURCE_GROUP" --location "$LOCATION"

# ── Azure Container Registry ────────────────────────
echo "Creating Container Registry..."
az acr create --resource-group "$RESOURCE_GROUP" --name "$ACR_NAME" --sku Basic --admin-enabled true
ACR_PASSWORD=$(az acr credential show --name "$ACR_NAME" --query "passwords[0].value" -o tsv)

# ── Azure Cache for Redis ───────────────────────────
echo "Creating Azure Cache for Redis..."
az redis create \
  --resource-group "$RESOURCE_GROUP" \
  --name "$REDIS_NAME" \
  --location "$LOCATION" \
  --sku Basic \
  --vm-size c0 \
  --enable-non-ssl-port false

REDIS_HOST=$(az redis show --name "$REDIS_NAME" --resource-group "$RESOURCE_GROUP" --query "hostName" -o tsv)
REDIS_KEY=$(az redis list-keys --name "$REDIS_NAME" --resource-group "$RESOURCE_GROUP" --query "primaryKey" -o tsv)


# ── Identity & Key Vault ────────────────────────────
IDENTITY_NAME="rankroute-identity"
echo "Creating User-Assigned Identity..."
az identity create --name "$IDENTITY_NAME" --resource-group "$RESOURCE_GROUP" --location "$LOCATION"
IDENTITY_ID=$(az identity show --name "$IDENTITY_NAME" --resource-group "$RESOURCE_GROUP" --query "id" -o tsv)
IDENTITY_PRINCIPAL_ID=$(az identity show --name "$IDENTITY_NAME" --resource-group "$RESOURCE_GROUP" --query "principalId" -o tsv)

KV_NAME="rr-kv-${RANDOM}"
echo "Creating Key Vault ($KV_NAME)..."
az keyvault create --name "$KV_NAME" --resource-group "$RESOURCE_GROUP" --location "$LOCATION" --enable-rbac-authorization false
az keyvault set-policy --name "$KV_NAME" --object-id "$IDENTITY_PRINCIPAL_ID" --secret-permissions get list
KV_URI="https://$KV_NAME.vault.azure.net"

echo "Storing secrets in Key Vault..."
az keyvault secret set --vault-name "$KV_NAME" --name "redis-url" --value "redis://:$REDIS_KEY@$REDIS_HOST:6380/0?ssl=True" > /dev/null
az keyvault secret set --vault-name "$KV_NAME" --name "supabase-url" --value "$SUPABASE_URL" > /dev/null
az keyvault secret set --vault-name "$KV_NAME" --name "supabase-service-key" --value "$SUPABASE_SERVICE_KEY" > /dev/null
az keyvault secret set --vault-name "$KV_NAME" --name "supabase-jwt-secret" --value "$SUPABASE_JWT_SECRET" > /dev/null
az keyvault secret set --vault-name "$KV_NAME" --name "supabase-anon-key" --value "$SUPABASE_ANON_KEY" > /dev/null
az keyvault secret set --vault-name "$KV_NAME" --name "groq-api-key" --value "$GROQ_API_KEY" > /dev/null
az keyvault secret set --vault-name "$KV_NAME" --name "tavily-api-key" --value "$TAVILY_API_KEY" > /dev/null
az keyvault secret set --vault-name "$KV_NAME" --name "agent-api-keys" --value "$AGENT_API_KEYS" > /dev/null
az keyvault secret set --vault-name "$KV_NAME" --name "huggingface-api-token" --value "${HUGGINGFACE_API_TOKEN:-}" > /dev/null

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
  --query "[0].value" -o tsv)

echo "Creating Azure Files Share..."
az storage share-rm create \
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

# ── Deploy Backend API ──────────────────────────────

echo "Granting identity access to ACR..."
ACR_ID=$(az acr show --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" --query "id" -o tsv)
az role assignment create --assignee "$IDENTITY_PRINCIPAL_ID" --scope "$ACR_ID" --role AcrPull

echo "Deploying API container..."
az containerapp create \
  --name "$BACKEND_ACA" \
  --resource-group "$RESOURCE_GROUP" \
  --environment "$ACA_ENV" \
  --image "$ACR_NAME.azurecr.io/rankroute-api:latest" \
  --registry-server "$ACR_NAME.azurecr.io" \
  --target-port 9000 \
  --ingress external \
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
    HUGGINGFACE_API_TOKEN=secretref:huggingface-api-token \
    FRONTEND_URL="$FRONTEND_URL" \
    DEBUG=false \
    LLM_PROVIDER=groq \
    PRIMARY_MODEL=llama-3.3-70b-versatile \
    FALLBACK_MODEL_1=llama-3.1-8b-instant \
    FALLBACK_MODEL_2=llama-3.1-8b-instant \
    CORS_ORIGINS="$FRONTEND_URL" \
    EMBEDDING_PROVIDER=huggingface \
    EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2 \
    CHROMA_HOST=rankroute-chromadb \
    CHROMA_PORT=8000 \
    CHROMA_AUTH_TOKEN=secretref:chroma-auth-token

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
API_FQDN=$(az containerapp show --name "$BACKEND_ACA" --resource-group "$RESOURCE_GROUP" --query "properties.configuration.ingress.fqdn" -o tsv)
echo "──────────────────────────────────────────────"
echo "✅ Deployment complete!"
echo "API URL: https://$API_FQDN"
echo "Frontend CORS origin: $FRONTEND_URL"
echo "──────────────────────────────────────────────"
echo ""
echo "Next steps:"
echo "  1. Configure custom domain + SSL: az containerapp hostname add ..."
echo "  2. Deploy frontend to Azure Static Web Apps or Vercel"
echo "  3. Run V5__admin_logs.sql on Supabase"
