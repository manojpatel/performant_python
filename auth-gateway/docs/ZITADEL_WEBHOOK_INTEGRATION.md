# Zitadel Webhook Integration for OpenFGA Sync

## Overview

The auth-gateway now includes webhook endpoints that automatically sync users from Zitadel to OpenFGA. When users are created, updated, or deleted in Zitadel (via console or API), these webhooks ensure OpenFGA permissions stay in sync.

## Architecture

```
┌─────────────────────────────────────────┐
│         Zitadel Console/API             │
│                                         │
│  User Operations:                       │
│  • Create → Triggers Action             │
│  • Update → Triggers Action             │
│  • Delete → Triggers Action             │
└─────────────┬───────────────────────────┘
              │
              │ HTTP Webhook
              ▼
┌─────────────────────────────────────────┐
│          Auth Gateway                   │
│                                         │
│  Webhook Endpoints (No Auth):          │
│  POST /webhooks/user-created            │
│  POST /webhooks/user-updated            │
│  POST /webhooks/user-deleted            │
└─────────────┬───────────────────────────┘
              │
              │ Create Tuples
              ▼
┌─────────────────────────────────────────┐
│            OpenFGA                      │
│                                         │
│  Permissions auto-synced!               │
└─────────────────────────────────────────┘
```

---

## API Endpoints

### POST /webhooks/user-created

Automatically creates default permissions in OpenFGA when a new user is created in Zitadel.

**Request Body:**
```json
{
  "userId": "351983461357060103",
  "userName": "john.doe",
  "userType": "machine"  // or "human"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Synced user 351983461357060103 to OpenFGA (1 permissions created)"
}
```

**Default Permissions Created:**
- `user:{userId}` → `member` → `organization:default`

---

### POST /webhooks/user-updated

Acknowledges user updates (extend for role changes if needed).

**Request Body:**
```json
{
  "userId": "351983461357060103",
  "userName": "john.doe.updated"
}
```

**Response:**
```json
{
  "status": "acknowledged",
  "message": "User 351983461357060103 update acknowledged"
}
```

---

### POST /webhooks/user-deleted

Acknowledges user deletion. Future enhancement: clean up OpenFGA tuples.

**Request Body:**
```json
{
  "userId": "351983461357060103"
}
```

**Response:**
```json
{
  "status": "acknowledged",
  "message": "User 351983461357060103 deletion acknowledged"
}
```

> [!NOTE]
> Full tuple cleanup requires listing and deleting all permissions for the user. This is logged as a warning and can be implemented in a future enhancement.

---

## Configuring Zitadel Actions

To enable automatic sync, configure Zitadel Actions to call these webhooks:

### 1. Create Action in Zitadel Console

Navigate to: **Settings → Actions → New**

#### Action: User Created

```javascript
function userCreated(ctx, api) {
  const webhookUrl = 'http://auth-gateway:3000/webhooks/user-created';
  
  const payload = {
    userId: ctx.v1.user.id,
    userName: ctx.v1.user.userName,
    userType: ctx.v1.user.type  // "human" or "machine"
  };
  
  // Call webhook
  http.post(webhookUrl, {
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload)
  });
}
```

#### Action: User Updated

```javascript
function userUpdated(ctx, api) {
  const webhookUrl = 'http://auth-gateway:3000/webhooks/user-updated';
  
  const payload = {
    userId: ctx.v1.user.id,
    userName: ctx.v1.user.userName
  };
  
  http.post(webhookUrl, {
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload)
  });
}
```

#### Action: User Deleted

```javascript
function userDeleted(ctx, api) {
  const webhookUrl = 'http://auth-gateway:3000/webhooks/user-deleted';
  
  const payload = {
    userId: ctx.v1.deletedUser.id
  };
  
  http.post(webhookUrl, {
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload)
  });
}
```

### 2. Attach Actions to Flows

In Zitadel Console:
1. Go to **Settings → Flows**
2. Find the appropriate flow triggers:
   - **User Created** → Pre-creation or Post-creation
   - **User Updated** → Post-update
   - **User Deleted** → Pre-deletion or Post-deletion
3. Attach the corresponding action

---

## Customizing Default Permissions

Edit `auth-gateway/src/webhooks.rs`:

```rust
fn get_default_permissions() -> Vec<(String, String)> {
    vec![
        ("member".to_string(), "organization:default".to_string()),
        ("viewer".to_string(), "feature:basic_access".to_string()),
        // Add more default permissions as needed
    ]
}
```

---

## Testing

### Manual Test

```bash
python3 auth-gateway/test-scripts/test_webhooks.py
```

### Example with curl

```bash
# Simulate user creation
curl -X POST http://localhost:3000/webhooks/user-created \
  -H "Content-Type: application/json" \
  -d '{"userId":"test-123","userName":"test.user","userType":"machine"}'

# Response:
# {"status":"success","message":"Synced user test-123 to OpenFGA (1 permissions created)"}
```

---

## Security Considerations

> [!WARNING]
> **Current Implementation**: Webhook endpoints bypass authentication to allow Zitadel Actions to call them.

**For Production:**

1. **Add Webhook Secret Validation**:
   ```rust
   // Validate X-Webhook-Secret header
   let secret = req.headers().get("X-Webhook-Secret");
   if secret != expected_secret {
       return Err(StatusCode::UNAUTHORIZED);
   }
   ```

2. **Use Private Network**: Ensure webhooks are only accessible from your internal network (not public internet).

3. **Add Rate Limiting**: Protect against webhook spam.

---

## Troubleshooting

### Webhook returns 5xx error
- Check auth-gateway logs: `tail -f auth-gateway/gateway.log`
- Verify `OPENFGA_STORE_ID` environment variable is set
- Ensure OpenFGA is running and accessible

### Permissions not created
- Check OpenFGA console to verify tuples
- Review webhook response message for error details
- Verify default permissions are configured correctly

### Zitadel Action fails
- Check Zitadel Action logs in console
- Verify webhook URL is correct (use internal Docker network name if in containers)
- Ensure auth-gateway is running and accessible

---

## Future Enhancements

1. **Full Tuple Cleanup**: Implement OpenFGA Read API to list and delete all user tuples on deletion
2. **Role-Based Sync**: Update permissions when user roles change
3. **Batch Sync**: Add endpoint for bulk user sync (migration scenarios)
4. **Webhook Signature Verification**: Add HMAC validation for production security
5. **Idempotency**: Handle duplicate webhook calls gracefully
