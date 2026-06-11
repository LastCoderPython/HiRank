# RankRoute — Azure Deployment Guide

## Architecture

```
                          Internet
                             │
                    ┌────────▼────────┐
                    │   Custom Domain │
                    │   (your-domain) │
                    └────────┬────────┘
                             │ HTTPS
               ┌─────────────▼──────────────┐
               │   Azure Container Apps     │
               │   Environment (ACA Env)    │
               │                            │
               │  ┌──────────────────────┐  │
               │  │  rankroute-api       │  │  ◄── HTTP ingress (port 9000)
               │  │  FastAPI + Gunicorn  │  │       scales 1–3 replicas
               │  └──────────┬───────────┘  │
               │             │              │
               │  ┌──────────▼───────────┐  │
               │  │  rankroute-worker    │  │  ◄── Celery worker (no ingress)
               │  │  ingestion queue     │  │       always 1 replica
               │  └──────────┬───────────┘  │
               │             │              │
               │  ┌──────────▼───────────┐  │
               │  │  rankroute-beat      │  │  ◄── Celery Beat (no ingress)
               │  │  weekly cron         │  │       always 1 replica
               │  └──────────────────────┘  │
               └─────────────┬──────────────┘
                             │
               ┌─────────────▼──────────────┐
               │  Azure Cache for Redis     │
               │  (Basic tier, SSL 6380)   │
               └────────────────────────────┘

          External Services (not deployed on Azure):
            ┌────────────┐  ┌──────────────────┐
            │  Supabase  │  │  Groq / Tavily   │
            │  (Auth+DB) │  │  (LLM + Search)  │
            └────────────┘  └──────────────────┘
```

## Prerequisites

1. **Azure CLI** installed and logged in: `az login`
2. **GitHub repo** with the code pushed
3. **Supabase project** (already set up)
4. **Groq API key**, **Tavily API key**
5. **Docker** installed (for local testing)

## Step 1: Set Environment Variables

```bash
# Set production secrets as shell variables
export SUPABASE_URL="https://your-project.supabase.co/rest/v1/"
export SUPABASE_SERVICE_KEY="your_service_role_key"
export SUPABASE_JWT_SECRET="your_jwt_secret"
export SUPABASE_ANON_KEY="your_anon_key"
export GROQ_API_KEY="your_groq_key"
export TAVILY_API_KEY="your_tavily_key"
export AGENT_API_KEYS="your_agent_api_key"
export FRONTEND_URL="https://your-frontend-domain.com"
```

## Step 2: Provision Infrastructure

```bash
cd infrastructure/azure
chmod +x deploy.sh
./deploy.sh
```

This creates:
- Resource group `rankroute-prod`
- Azure Container Registry `rankrouteacr`
- Azure Cache for Redis (Basic tier, ~$15/month)
- Container Apps Environment
- 3 Container Apps (api, worker, beat)
- Builds and pushes Docker images

## Step 3: Configure Custom Domain + SSL

```bash
# Replace with your actual domain
DOMAIN="api.your-domain.com"
CERT_ID="/subscriptions/$(az account show --query id -o tsv)/resourceGroups/rankroute-prod/providers/Microsoft.App/managedEnvironments/rankroute-env"

# Add custom domain
az containerapp hostname add \
  --name rankroute-api \
  --resource-group rankroute-prod \
  --hostname "$DOMAIN"

# Upload certificate (or let ACA auto-manage it)
# See: https://learn.microsoft.com/en-us/azure/container-apps/custom-domains-managed-certificates
```

## Step 4: Database Migration

Run the admin_logs migration on Supabase:

```sql
-- Execute in Supabase SQL Editor
CREATE TABLE IF NOT EXISTS public.admin_logs (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type  TEXT NOT NULL,
    severity    TEXT NOT NULL CHECK (severity IN ('info', 'warning', 'error', 'critical')),
    actor_id    TEXT,
    actor_role  TEXT NOT NULL DEFAULT 'system',
    summary     TEXT NOT NULL,
    details     JSONB,
    source      TEXT NOT NULL DEFAULT '',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_admin_logs_event_type ON public.admin_logs(event_type);
CREATE INDEX IF NOT EXISTS idx_admin_logs_severity   ON public.admin_logs(severity);
CREATE INDEX IF NOT EXISTS idx_admin_logs_created_at ON public.admin_logs(created_at DESC);
```

## Step 5: Promote Admin User

```sql
UPDATE public.profiles SET role = 'admin' WHERE email = 'your@email.com';
```

## Step 6: Deploy Frontend

Deploy the Next.js frontend to **Azure Static Web Apps** or **Vercel**:

### Option A: Azure Static Web Apps (free tier)

```bash
cd frontend
npx swa init --yes
npx swa deploy --env production
```

Set these env vars in the SWA config:
- `NEXT_PUBLIC_API_URL=https://api.your-domain.com`

### Option B: Vercel (simpler)

```bash
cd frontend
npx vercel --prod
```

Set env var in Vercel dashboard:
- `NEXT_PUBLIC_API_URL=https://api.your-domain.com`

## Step 7: Verify Deployment

```bash
# Health check
curl https://api.your-domain.com/api/health

# Should return 200 with full system status
```

## CI/CD

The workflow `.github/workflows/deploy-azure.yml` auto-deploys on every push to `main`:

1. Runs all 136+ unit tests
2. Builds Docker image via ACR
3. Updates all 3 Container Apps

**Setup GitHub secrets:**
| Secret | Value |
|--------|-------|
| `AZURE_CREDENTIALS` | Output of `az ad sp create-for-rbac --name rankroute-deploy --role contributor --scopes /subscriptions/$(az account show --query id -o tsv)/resourceGroups/rankroute-prod --sdk-auth` |

## Costs (approximate monthly)

| Service | Tier | Cost |
|---------|------|------|
| Azure Container Registry | Basic | ~$5 |
| Azure Cache for Redis | Basic (C0) | ~$15 |
| Container Apps (3 apps) | Consumption | ~$10–$50 (depends on traffic) |
| Azure Static Web Apps | Free | $0 |
| **Total** | | **~$30–$70/month** |

To reduce costs:
- Set `--min-replicas 0` on the API (scales to zero when idle)
- Downsize Redis to the free tier doesn't exist, but C0 Basic is the minimum

## Troubleshooting

### "Failed to fetch" on frontend
- Check `NEXT_PUBLIC_API_URL` matches the ACA FQDN or custom domain
- Verify CORS_ORIGINS includes the frontend domain
- Wait 2–3 minutes after deployment for ACA ingress to propagate

### Worker not processing tasks
- Check Redis connection: `REDIS_URL` secret might be wrong
- Verify worker logs: `az containerapp logs show --name rankroute-worker --resource-group rankroute-prod`

### Embeddings failing
- The `all-MiniLM-L6-v2` model downloads on first startup (~80MB)
- First request may be slow (10–20s); subsequent requests use cached model
- ACA needs `--memory 2.0Gi` for the embedding model to load

### ChromaDB data persistence
- ACA does not persist local filesystem across restarts by default
- To preserve ChromaDB data between deployments, attach an Azure Files share:
  - See: [Mount Azure Files in ACA](https://learn.microsoft.com/en-us/azure/container-apps/storage-mounts)
  - Mount `/app/data` to a persistent volume
