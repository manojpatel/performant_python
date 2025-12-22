# End-to-End Gateway Testing

This document explains how to run the comprehensive end-to-end test for the auth-gateway.

## Overview

The `test_e2e_auth_gateway.py` script performs a complete test cycle:

1. **Creates a test user** via `auth-gateway` → `Zitadel`
2. **Generates a PAT** (Personal Access Token) via `auth-gateway` → `Zitadel`
3. **Sets up authorization** via `auth-gateway` → `OpenFGA`
4. **Runs tests** (authentication, authorization, rate limiting)
5. **Cleans up** by deleting the test user via `auth-gateway` → `Zitadel`

**Key Point**: All operations go through the auth-gateway (port 3000), which proxies requests to Zitadel and OpenFGA based on the access rules defined in `auth-gateway/access_rules.json`.

## Architecture

```
Test Script
    ↓
Auth Gateway (port 3000)
    ├─→ /oauth/v2/token → Zitadel (authentication)
    ├─→ /v2/users/* → Zitadel (user management)
    └─→ /stores/* → OpenFGA (authorization)
```

## Prerequisites

### 1. All Services Running

```bash
docker compose up -d
```

Verify:
```bash
docker compose ps
```

### 2. Auth Gateway Rebuilt

After updating the access rules and code:

```bash
docker compose build auth-gateway
docker compose up -d auth-gateway
```

### 3. Zitadel Service Account

You need a service account in Zitadel with client credentials:

#### Option A: Manual Setup (Recommended)

1. Access Zitadel UI (use SSH port forwarding if on remote server):
   ```bash
   ssh -L 8081:localhost:8081 ubuntu@YOUR_SERVER
   ```

2. Open http://localhost:8081 in your LOCAL browser

3. Login: `zitadel-admin@zitadel.localhost` / `Password1!`

4. Create a Service Account:
   - Go to your project (or create one)
   - Click **Applications** → **New**
   - Select **API** application type
   - Name: `e2e-test-client`
   - Authentication Method: **Basic**

5. Note the **Client ID** and **Client Secret**

6. Set environment variables:
   ```bash
   export ZITADEL_CLIENT_ID='your_client_id_here'
   export ZITADEL_CLIENT_SECRET='your_client_secret_here'
   ```

#### Option B: Use Existing Admin Token

If you already have an admin token, you can modify the script to use it directly:

```python
# In test_e2e_auth_gateway.py, modify get_admin_token():
def get_admin_token() -> Optional[str]:
    # Hardcode your token for testing
    return "YOUR_ADMIN_TOKEN_HERE"
```

## Running the Test

Once you have the service account set up:

```bash
cd /home/ubuntu/performant_python

# Set credentials
export ZITADEL_CLIENT_ID='your_client_id'
export ZITADEL_CLIENT_SECRET='your_client_secret'

# Run the test
python3 auth-gateway/test-scripts/test_e2e_auth_gateway.py
```

## Expected Output

```
================================================================================
  End-to-End Auth Gateway Test
================================================================================
All operations go through the auth-gateway (port 3000)
Gateway proxies to Zitadel and OpenFGA based on access rules

→ Getting admin token from Zitadel...
  ✅ Got admin token: eyJhbGciOiJSUzI1NiIsImtpZCI6...

→ Creating test user...
  ✅ Created user: 123456789012345678

→ Generating Personal Access Token...
  ✅ Generated PAT: dEnxhbGciOiJSUzI1NiIsImtpZCI6...

→ Setting up OpenFGA authorization rules...
  ✅ Set up authorization rules

================================================================================
  Running Gateway Tests
================================================================================

→ Testing authentication...
  ✅ Authentication passed (status: 200)

→ Testing rate limiting (sending 110 requests)...
  ✅ Rate limit triggered at request #101

================================================================================
  Cleanup
================================================================================

→ Deleting test user...
  ✅ Deleted test user

================================================================================
  Test Summary
================================================================================
  Authentication Test: ✅ PASS
  Rate Limiting Test:  ✅ PASS
```

## Access Rules Configuration

The test relies on these access rules in `auth-gateway/access_rules.json`:

```json
[
    {
        "path": "/oauth/v2/token",
        "method": "POST",
        "feature": "public_access",
        "target": "zitadel"
    },
    {
        "path": "/v2/users/human",
        "method": "POST",
        "feature": "user_management",
        "target": "zitadel"
    },
    {
        "path": "/v2/users/*path/pat",
        "method": "POST",
        "feature": "user_management",
        "target": "zitadel"
    },
    {
        "path": "/v2/users/*path",
        "method": "DELETE",
        "feature": "user_delete",
        "target": "zitadel"
    },
    {
        "path": "/stores/*path",
        "method": "POST",
        "feature": "authorization_management",
        "target": "openfga"
    }
]
```

## Troubleshooting

### Error: "ZITADEL_CLIENT_ID and ZITADEL_CLIENT_SECRET must be set"

**Solution**: Set up a service account in Zitadel (see Prerequisites above)

### Error: "Failed to get token: 400"

**Possible causes**:
- Invalid client credentials
- Client doesn't have proper scopes

**Solution**: Verify your client ID and secret are correct

### Error: "Failed to create user: 403"

**Possible causes**:
- Admin token doesn't have user management permissions
- Token is expired

**Solution**: Ensure your service account has proper permissions in Zitadel

### Error: "Failed to set up rules: 404"

**Possible causes**:
- OpenFGA store ID is incorrect
- OpenFGA is not running

**Solution**: 
1. Check OpenFGA is running: `docker compose ps openfga`
2. Get the correct store ID from OpenFGA
3. Update the script with the correct store ID

### Rate limiting not triggered

**Possible causes**:
- Requests are failing before reaching rate limit logic
- Redis/Valkey is not running

**Solution**:
1. Check Valkey: `docker compose ps valkey`
2. Ensure authentication is passing first

## Simplified Testing (Without Full E2E)

If you can't set up the full E2E test, you can test individual components:

### Test 1: Gateway is Running
```bash
curl -v http://localhost:3000/api/finance/reports
# Should return: 401 Unauthorized
```

### Test 2: Public Endpoint (No Auth Required)
```bash
curl -v http://localhost:3000/.well-known/openid-configuration
# Should return: 200 OK with Zitadel's OIDC configuration
```

### Test 3: With Manual Token
```bash
# Get a token manually from Zitadel
TOKEN="your_token_here"

# Test authenticated request
curl -H "Authorization: Bearer $TOKEN" http://localhost:3000/api/finance/reports
```

## Next Steps

After successful E2E testing:

1. **Add more test scenarios** (different users, permissions, etc.)
2. **Integrate with CI/CD** pipeline
3. **Add performance benchmarks**
4. **Monitor in production** with proper observability

## Related Documentation

- `TESTING_AUTH_GATEWAY.md` - Manual testing guide
- `GATEWAY_TESTING_SOLUTIONS.md` - Troubleshooting solutions
- `auth-gateway/README.md` - Gateway architecture and configuration
