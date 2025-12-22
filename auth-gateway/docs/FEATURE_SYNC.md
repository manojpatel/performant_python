# Feature Sync System

## Overview

The auth-gateway automatically detects and migrates OpenFGA tuples when features in `access_rules.json` are renamed or deleted.

## How It Works

```
CI/CD Pipeline
    ↓
Deploys two files:
  • access_rules.json (latest)
  • access_rules_prev.json (previous)
    ↓
Auth Gateway Startup
    ↓
feature_sync::migrate_features()
  1. Load both JSON files
  2. Compare features
  3. Detect changes:
     - Renames (same endpoint, different feature)
     - Deletions (in prev, not in latest)
     - Additions (in latest, not in prev)  
  4. Migrate OpenFGA:
     - Renames: Update all tuples to new feature name
     - Deletions: Clean up all tuples
    ↓
Load latest access_rules.json
    ↓
Start serving requests
```

## Example: Feature Rename

**Previous (`access_rules_prev.json`):**
```json
{
  "path": "/api/*path",
  "method": "GET",
  "feature": "feature:report_viewer"
}
```

**Latest (`access_rules.json`):**
```json
{
  "path": "/api/*path",
  "method": "GET",
  "feature": "feature:reporting"
}
```

**What Happens:**
1. Gateway detects the same endpoint has a different feature name
2. Identifies this as a rename: `feature:report_viewer` → `feature:reporting`
3. Migrates all OpenFGA tuples:
   ```
   BEFORE: user:123 → viewer → feature:report_viewer
   AFTER:  user:123 → viewer → feature:reporting
   ```

## CI/CD Integration

Your CI/CD pipeline should:

```bash
# 1. Backup current production version
kubectl cp auth-gateway-pod:/app/access_rules.json ./access_rules_prev.json

# 2. Deploy both files
kubectl create configmap access-rules \
  --from-file=access_rules.json=./new_access_rules.json \
  --from-file=access_rules_prev.json=./access_rules_prev.json \
  --dry-run=client -o yaml | kubectl apply -f -

# 3. Restart gateway (triggers migration)
kubectl rollout restart deployment/auth-gateway
```

## Logs

On startup, the gateway logs migration activity:

```
INFO Running feature migration check...
INFO Feature changes detected:
INFO   Renamed: [("feature:report_viewer", "feature:reporting")]
INFO   Deleted: []
INFO   Added: []
INFO Migrating feature tuples: feature:report_viewer → feature:reporting
INFO Found 5 tuples to migrate
INFO Successfully migrated 5/5 tuples from feature:report_viewer to feature:reporting
INFO Feature migration completed successfully
```

## Safety

- ✅ **Non-blocking**: Migration failure doesn't prevent startup
- ✅ **Logged**: All actions are logged for audit
- ✅ **Atomic**: Each tuple migration is independent
- ✅ **Idempotent**: Safe to run multiple times

## Customization

To change how renames are detected, edit `feature_sync.rs:detect_renames()`:

```rust
fn detect_renames(prev: &[AccessRule], latest: &[AccessRule]) -> Vec<(String, String)> {
    // Current: same path+method = rename
    // Customize this logic as needed
}
```

## Testing Locally

```bash
cd auth-gateway

# Create test files
echo '[{...}]' > access_rules_prev.json  # Old feature name
echo '[{...}]' > access_rules.json       # New feature name

# Run gateway
cargo run

# Check logs for migration activity
```
