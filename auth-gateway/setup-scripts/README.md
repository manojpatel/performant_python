# Setup & Utility Scripts

This directory contains scripts for bootstrapping, updating, and managing the Auth Gateway infrastructure (OpenFGA, Zitadel).

## 🚀 OpenFGA Scripts

### 1. `setup_openfga.py`
**Purpose**: Bootstraps a fresh OpenFGA store from scratch.
- Creates a new Store.
- Validates the model definition against tests.
- Uploads the model.
- Seeds initial tuples.

**Usage**:
```bash
python3 setup_openfga.py \
  --model ../openfga/model.fga \
  --tests ../openfga/tests.fga.yaml \
  --tuples ../openfga/seed_tuples.yaml
```

### 2. `update_openfga_model.py`
**Purpose**: Safely updates an existing OpenFGA store's authorization model.
- **Validates** backward compatibility using `fga model test`.
- Aborts if validation fails.
- Uploads the new model version.

**Usage**:
```bash
python3 update_openfga_model.py \
  --model ../openfga/model.fga \
  --tests ../openfga/tests.fga.yaml
```

### 3. `rollback_openfga_model.py`
**Purpose**: Reverts the OpenFGA store to a previous authorization model version.
- Lists the last 5 model versions.
- Asks for confirmation before rolling back.
- Updates the store to use the selected older model ID.

**Usage**:
```bash
python3 rollback_openfga_model.py
```

---

## 🔐 Authentication Scripts

### 4. `get_access_token.py`
**Purpose**: Utilities to fetch valid OAuth2 access tokens from Zitadel for testing.
- Supports Client Credentials flow (Machine-to-Machine).
- Supports Resource Owner Password flow (User).

**Usage**:
```bash
# Get token for a service account
python3 get_access_token.py --type client_credentials

# Get token for a specific user
python3 get_access_token.py --type password --username myuser --password mypass
```

### 5. `setup_zitadel.py`
**Purpose**: Automates the configuration of Zitadel.
- Creates Organizations, Projects, and Applications.
- Sets up Service Users and Roles.
- Generates key files for the Auth Gateway.

**Usage**:
```bash
python3 setup_zitadel.py
```

### 6. `get_zitadel_pat_token.py`
**Purpose**: Generates a long-lived Personal Access Token (PAT) for a Service User.
- Requires an Admin Token (from `setup_zitadel.py` or manually obtained).
- Useful for configuring services that need to call Zitadel/Gateway APIs.

**Usage**:
```bash
python3 get_zitadel_pat_token.py \
  --admin-token-file zitadel_admin_token.txt \
  --user-id <SERVICE_USER_ID>
```
