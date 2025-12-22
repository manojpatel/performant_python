# Zitadel Setup Guide

This guide walks you through setting up Zitadel for local development with the auth-gateway.

## Prerequisites

Make sure Zitadel is running:
```bash
docker compose up -d zitadel
```

Wait for Zitadel to be ready, then access it at: http://localhost:8081

## Step 1: Initial Login

1. Navigate to http://localhost:8081
2. Complete the initial setup wizard:
   - Create an organization (e.g., "Dev Org")
   - Create an admin user
   - Set a password

## Step 2: Create a Service Account (Machine User)

This service account will be used by the test scripts to authenticate.

1. Go to **Users** in the left sidebar
2. Click **+ New**
3. Select **Machine**
4. Fill in:
   - **User Name**: `test-service-account`
   - **Name**: `Test Service Account`
   - **Description**: `Service account for E2E testing`
5. Click **Create**

## Step 3: Create an Application for the Service Account

1. After creating the machine user, you'll be on the user details page
2. Scroll down to the **Applications** section
3. Click **+ New**
4. Fill in:
   - **Name**: `test-client`
   - **Type**: Select **API** (this is for client credentials flow)
5. Click **Continue**

### Configure Authentication Method

1. **Authentication Method**: Select **Client Secret (Basic Auth)** or **JWT with Private Key**
   - For simplicity, use **Client Secret (Basic Auth)**
2. Click **Continue**

### Review and Create

1. Review the settings
2. Click **Create**
3. **IMPORTANT**: You'll see the **Client ID** and **Client Secret**
   - **Copy these immediately** - the secret won't be shown again!
   - Save them to your `.env` file or export them

```bash
export ZITADEL_CLIENT_ID='<your-client-id>@<your-project-id>'
export ZITADEL_CLIENT_SECRET='<your-client-secret>'
```

## Step 4: Configure Development Mode (Fix HTTP Redirect Error)

> [!IMPORTANT]
> This step is critical to fix the "redirect_uri is http and is not allowed" error.

Even though we're using client credentials flow (which doesn't use redirect URIs), Zitadel still enforces security policies. For local development:

### Option A: Enable Development Mode (Recommended for Local Dev)

1. Go back to your application (`test-client`)
2. In the application settings, find **Development Mode** or **Allow Insecure**
3. **Enable** the development/insecure mode toggle
4. **Save** changes

### Option B: Use HTTPS Locally (Production-like)

If you want to simulate production:
1. Set up a local HTTPS proxy (e.g., using nginx or Caddy)
2. Update redirect URIs to use `https://`
3. Configure `ZITADEL_EXTERNALSECURE=true` in docker-compose.yml

## Step 5: Grant Required Permissions

The service account needs permission to manage users and access Zitadel APIs.

### Grant Organization Manager Role

1. Go to **Organization** → **+ (add member)**
2. Search for your service account (`test-service-account`)
3. Assign role: **Org Owner** or **User Manager**
4. Click **Add**

### Grant Project Roles (if needed)

1. Go to **Projects** → Find the Zitadel project
2. **Authorizations** → **+ New**
3. Select your service account
4. Grant necessary roles (e.g., `Project Owner`)

## Step 6: Test the Setup

Run the E2E test script:

```bash
cd /home/ubuntu/performant_python
export ZITADEL_CLIENT_ID='<your-client-id>'
export ZITADEL_CLIENT_SECRET='<your-client-secret>'
python auth-gateway/test-scripts/test_e2e_auth_gateway.py
```

## Troubleshooting

### Error: "redirect_uri is http and is not allowed"

**Cause**: The OAuth client application is not configured for development mode.

**Solution**: 
- Go to your application settings in Zitadel
- Enable **Development Mode** / **Allow Insecure** toggle
- Save changes

### Error: "invalid_client"

**Causes**:
- Wrong client ID or secret
- Client ID format should include project ID: `<client-id>@<project-id>`

**Solution**:
- Verify your credentials
- Check that you're using the full client ID with project suffix

### Error: "insufficient permissions" or "forbidden"

**Cause**: Service account doesn't have required permissions.

**Solution**:
- Grant **Org Owner** or **User Manager** role to the service account
- Ensure the service account has access to the required projects

### Connection Refused

**Cause**: Zitadel is not running or not ready.

**Solution**:
```bash
docker compose up -d zitadel
docker compose logs -f zitadel  # Wait for "Zitadel started" message
```

## Environment Variables Reference

Add these to your `.env` file:

```bash
# Zitadel Service Account Credentials
ZITADEL_CLIENT_ID=<your-client-id>@<your-project-id>
ZITADEL_CLIENT_SECRET=<your-client-secret>

# Zitadel Configuration (already in docker-compose.yml)
ZITADEL_EXT_PORT=8081
ZITADEL_MASTERKEY=MasterkeyNeedsToHave32Characters
```

## Next Steps

Once setup is complete:
1. Run the E2E tests: `python auth-gateway/test-scripts/test_e2e_auth_gateway.py`
2. Test the gateway: `python auth-gateway/test-scripts/test_auth_gateway.py`
3. Access the Zitadel console: http://localhost:8081
