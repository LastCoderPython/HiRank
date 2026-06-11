with open('infrastructure/azure/deploy.sh', 'r', encoding='utf-8') as f:
    content = f.read()

# Insert Identity and Key Vault creation before Container Apps Environment
kv_code = """
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
"""

content = content.replace('# ── Container Apps Environment ──────────────────────', kv_code + '\n# ── Container Apps Environment ──────────────────────')

# Update backend ACA
old_backend_secrets = """  --secrets \\
    redis-url="redis://:$REDIS_KEY@$REDIS_HOST:6380/0?ssl=True" \\
    supabase-url="$SUPABASE_URL" \\
    supabase-service-key="$SUPABASE_SERVICE_KEY" \\
    supabase-jwt-secret="$SUPABASE_JWT_SECRET" \\
    supabase-anon-key="$SUPABASE_ANON_KEY" \\
    groq-api-key="$GROQ_API_KEY" \\
    tavily-api-key="$TAVILY_API_KEY" \\
    agent-api-keys="$AGENT_API_KEYS" \\"""

new_backend_secrets = """  --user-assigned "$IDENTITY_ID" \\
  --registry-identity "$IDENTITY_ID" \\
  --secrets \\
    redis-url="keyvaultref:$KV_URI/secrets/redis-url,identityref:$IDENTITY_ID" \\
    supabase-url="keyvaultref:$KV_URI/secrets/supabase-url,identityref:$IDENTITY_ID" \\
    supabase-service-key="keyvaultref:$KV_URI/secrets/supabase-service-key,identityref:$IDENTITY_ID" \\
    supabase-jwt-secret="keyvaultref:$KV_URI/secrets/supabase-jwt-secret,identityref:$IDENTITY_ID" \\
    supabase-anon-key="keyvaultref:$KV_URI/secrets/supabase-anon-key,identityref:$IDENTITY_ID" \\
    groq-api-key="keyvaultref:$KV_URI/secrets/groq-api-key,identityref:$IDENTITY_ID" \\
    tavily-api-key="keyvaultref:$KV_URI/secrets/tavily-api-key,identityref:$IDENTITY_ID" \\
    agent-api-keys="keyvaultref:$KV_URI/secrets/agent-api-keys,identityref:$IDENTITY_ID" \\
    huggingface-api-token="keyvaultref:$KV_URI/secrets/huggingface-api-token,identityref:$IDENTITY_ID" \\"""

content = content.replace(old_backend_secrets, new_backend_secrets)

# Add HUGGINGFACE_API_TOKEN to backend env-vars
content = content.replace('    AGENT_API_KEYS=secretref:agent-api-keys \\', '    AGENT_API_KEYS=secretref:agent-api-keys \\\n    HUGGINGFACE_API_TOKEN=secretref:huggingface-api-token \\')

# Update worker ACA
old_worker_secrets = """  --secrets \\
    redis-url="redis://:$REDIS_KEY@$REDIS_HOST:6380/0?ssl=True" \\
    supabase-url="$SUPABASE_URL" \\
    supabase-service-key="$SUPABASE_SERVICE_KEY" \\
    groq-api-key="$GROQ_API_KEY" \\
    tavily-api-key="$TAVILY_API_KEY" \\"""

new_worker_secrets = """  --user-assigned "$IDENTITY_ID" \\
  --registry-identity "$IDENTITY_ID" \\
  --secrets \\
    redis-url="keyvaultref:$KV_URI/secrets/redis-url,identityref:$IDENTITY_ID" \\
    supabase-url="keyvaultref:$KV_URI/secrets/supabase-url,identityref:$IDENTITY_ID" \\
    supabase-service-key="keyvaultref:$KV_URI/secrets/supabase-service-key,identityref:$IDENTITY_ID" \\
    groq-api-key="keyvaultref:$KV_URI/secrets/groq-api-key,identityref:$IDENTITY_ID" \\
    tavily-api-key="keyvaultref:$KV_URI/secrets/tavily-api-key,identityref:$IDENTITY_ID" \\
    huggingface-api-token="keyvaultref:$KV_URI/secrets/huggingface-api-token,identityref:$IDENTITY_ID" \\"""

content = content.replace(old_worker_secrets, new_worker_secrets)
content = content.replace('    TAVILY_API_KEY=secretref:tavily-api-key \\', '    TAVILY_API_KEY=secretref:tavily-api-key \\\n    HUGGINGFACE_API_TOKEN=secretref:huggingface-api-token \\')

# Update beat ACA
old_beat_secrets = """  --secrets \\
    redis-url="redis://:$REDIS_KEY@$REDIS_HOST:6380/0?ssl=True" \\
    supabase-url="$SUPABASE_URL" \\
    supabase-service-key="$SUPABASE_SERVICE_KEY" \\"""

new_beat_secrets = """  --user-assigned "$IDENTITY_ID" \\
  --registry-identity "$IDENTITY_ID" \\
  --secrets \\
    redis-url="keyvaultref:$KV_URI/secrets/redis-url,identityref:$IDENTITY_ID" \\
    supabase-url="keyvaultref:$KV_URI/secrets/supabase-url,identityref:$IDENTITY_ID" \\
    supabase-service-key="keyvaultref:$KV_URI/secrets/supabase-service-key,identityref:$IDENTITY_ID" \\"""

content = content.replace(old_beat_secrets, new_beat_secrets)

# Grant ACR access to identity so it can pull images
acr_grant = """
echo "Granting identity access to ACR..."
ACR_ID=$(az acr show --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" --query "id" -o tsv)
az role assignment create --assignee "$IDENTITY_PRINCIPAL_ID" --scope "$ACR_ID" --role AcrPull
"""
content = content.replace('echo "Deploying API container..."', acr_grant + '\necho "Deploying API container..."')

# Remove --registry-password since we use managed identity for ACR
content = content.replace('  --registry-password "$ACR_PASSWORD" \\\n', '')

with open('infrastructure/azure/deploy.sh', 'w', encoding='utf-8') as f:
    f.write(content)
print('Updated deploy.sh with Key Vault and Managed Identity for ACR')
