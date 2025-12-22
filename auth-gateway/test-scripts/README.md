# Test Suite

This directory contains verification scripts for the Auth Gateway, OpenFGA, and Webhook integrations.

## 🧪 Test Scripts

| Script | Description | Usage |
|--------|-------------|-------|
| `test_auth_gateway.py` | **Main Test Suite**. Verifies Gateway health, OpenFGA routing (multi-backend), Auth middleware, and Error handling. | `python3 auth-gateway/test-scripts/test_auth_gateway.py` |
| `test_webhooks.py` | Integration tests for User Lifecycle Webhooks (Create/Delete/Sync). | `python3 auth-gateway/test-scripts/test_webhooks.py` |
| `test_action_permissions.py` | Verifies specific action-based permissions in the OpenFGA model. | `python3 auth-gateway/test-scripts/test_action_permissions.py` |
| `test_e2e_auth_gateway.py` | End-to-End integration test suite testing the full flow from Token -> Gateway -> Upstream. | `python3 auth-gateway/test-scripts/test_e2e_auth_gateway.py` |

## 🚀 Running Tests

### 1. Functional Tests
Run the main suite to verify the gateway is routing correctly and enforcing auth:
```bash
python3 auth-gateway/test-scripts/test_auth_gateway.py
```
**Checks:**
- Gateway Health
- OpenFGA Multi-Backend Routing
- Auth Middleware Enforcement
- Error Handling

### 2. Webhook Integration
Verify that user changes in Zitadel correctly propagated to OpenFGA:
```bash
python3 auth-gateway/test-scripts/test_webhooks.py
```

### 3. Permission Checks
Verify complex permission logic (e.g. hierarchical roles):
```bash
python3 auth-gateway/test-scripts/test_action_permissions.py
```

## 📋 Prerequisites
- **Auth Gateway** must be running (`http://localhost:3000`).
- **OpenFGA** must be running (`http://localhost:8080` or `8889`).
- **Admin Token** must be available in `auth-gateway/setup-scripts/zitadel_admin_token.txt` (or valid environment variable).
