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

# ── Container Apps Environment ──────────────────────
echo "Creating Container Apps Environment..."
az containerapp env create \
  --name "$ACA_ENV" \
  --resource-group "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --logs-destination none

# ── Build Docker Images ─────────────────────────────
echo "Building and pushing Docker images..."
az acr build --registry "$ACR_NAME" --image rankroute-api:latest ../../backend/.
az acr build --registry "$ACR_NAME" --image rankroute-worker:latest --file ../../backend/Dockerfile --build-arg CMD="celery" ../../backend/.

# ── Deploy Backend API ──────────────────────────────
echo "Deploying API container..."
az containerapp create \
  --name "$BACKEND_ACA" \
  --resource-group "$RESOURCE_GROUP" \
  --environment "$ACA_ENV" \
  --image "$ACR_NAME.azurecr.io/rankroute-api:latest" \
  --registry-server "$ACR_NAME.azurecr.io" \
  --registry-password "$ACR_PASSWORD" \
  --target-port 9000 \
  --ingress external \
  --min-replicas 1 \
  --max-replicas 3 \
  --cpu 1.0 \
  --memory 2.0Gi \
  --secrets \
    redis-url="redis://:$REDIS_KEY@$REDIS_HOST:6380/0?ssl=True" \
    supabase-url="$SUPABASE_URL" \
    supabase-service-key="$SUPABASE_SERVICE_KEY" \
    supabase-jwt-secret="$SUPABASE_JWT_SECRET" \
    supabase-anon-key="$SUPABASE_ANON_KEY" \
    groq-api-key="$GROQ_API_KEY" \
    tavily-api-key="$TAVILY_API_KEY" \
    agent-api-keys="$AGENT_API_KEYS" \
  --env-vars \
    REDIS_URL=secretref:redis-url \
    SUPABASE_URL=secretref:supabase-url \
    SUPABASE_SERVICE_KEY=secretref:supabase-service-key \
    SUPABASE_JWT_SECRET=secretref:supabase-jwt-secret \
    SUPABASE_ANON_KEY=secretref:supabase-anon-key \
    GROQ_API_KEY=secretref:groq-api-key \
    TAVILY_API_KEY=secretref:tavily-api-key \
    AGENT_API_KEYS=secretref:agent-api-keys \
    FRONTEND_URL="$FRONTEND_URL" \
    DEBUG=false \
    LLM_PROVIDER=groq \
    PRIMARY_MODEL=llama-3.3-70b-versatile \
    FALLBACK_MODEL_1=llama-3.1-8b-instant \
    FALLBACK_MODEL_2=llama-3.1-8b-instant \
    CORS_ORIGINS="$FRONTEND_URL" \
    EMBEDDING_PROVIDER=huggingface \
    EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2

# ── Deploy Celery Worker ────────────────────────────
echo "Deploying Worker container..."
az containerapp create \
  --name "$WORKER_ACA" \
  --resource-group "$RESOURCE_GROUP" \
  --environment "$ACA_ENV" \
  --image "$ACR_NAME.azurecr.io/rankroute-api:latest" \
  --registry-server "$ACR_NAME.azurecr.io" \
  --registry-password "$ACR_PASSWORD" \
  --command "celery" "-A" "app.worker:celery_app" "worker" "--loglevel=info" "--queues=ingestion" "--concurrency=2" \
  --min-replicas 1 \
  --max-replicas 1 \
  --cpu 0.5 \
  --memory 1.0Gi \
  --secrets \
    redis-url="redis://:$REDIS_KEY@$REDIS_HOST:6380/0?ssl=True" \
    supabase-url="$SUPABASE_URL" \
    supabase-service-key="$SUPABASE_SERVICE_KEY" \
    groq-api-key="$GROQ_API_KEY" \
    tavily-api-key="$TAVILY_API_KEY" \
  --env-vars \
    REDIS_URL=secretref:redis-url \
    SUPABASE_URL=secretref:supabase-url \
    SUPABASE_SERVICE_KEY=secretref:supabase-service-key \
    GROQ_API_KEY=secretref:groq-api-key \
    TAVILY_API_KEY=secretref:tavily-api-key \
    DEBUG=false

# ── Deploy Celery Beat ──────────────────────────────
echo "Deploying Beat container..."
az containerapp create \
  --name "$BEAT_ACA" \
  --resource-group "$RESOURCE_GROUP" \
  --environment "$ACA_ENV" \
  --image "$ACR_NAME.azurecr.io/rankroute-api:latest" \
  --registry-server "$ACR_NAME.azurecr.io" \
  --registry-password "$ACR_PASSWORD" \
  --command "celery" "-A" "app.worker:celery_app" "beat" "--loglevel=info" \
  --min-replicas 1 \
  --max-replicas 1 \
  --cpu 0.25 \
  --memory 0.5Gi \
  --secrets \
    redis-url="redis://:$REDIS_KEY@$REDIS_HOST:6380/0?ssl=True" \
    supabase-url="$SUPABASE_URL" \
    supabase-service-key="$SUPABASE_SERVICE_KEY" \
  --env-vars \
    REDIS_URL=secretref:redis-url \
    SUPABASE_URL=secretref:supabase-url \
    SUPABASE_SERVICE_KEY=secretref:supabase-service-key

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
