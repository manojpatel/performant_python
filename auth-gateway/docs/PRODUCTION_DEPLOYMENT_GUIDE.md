# Auth Gateway Production Deployment Guide

**Complete step-by-step guide to deploy the Auth Gateway system in production**

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Prerequisites](#prerequisites)
3. [Zitadel Setup](#zitadel-setup)
4. [OpenFGA Setup](#openfga-setup)
5. [Auth Gateway Deployment](#auth-gateway-deployment)
6. [CI/CD Configuration](#cicd-configuration)
7. [Monitoring & Maintenance](#monitoring--maintenance)
8. [Troubleshooting](#troubleshooting)

---

## Architecture Overview

```
┌──────────────┐
│   Clients    │
└──────┬───────┘
       │
       ▼
┌──────────────────────────────────┐
│      Auth Gateway (Port 3000)    │
│  • JWT Validation                │
│  • Rate Limiting                 │
│  • OpenFGA Authorization         │
│  • Proxy Routing                 │
└──────┬──────────────┬────────────┘
       │              │
       ▼              ▼
┌─────────────┐  ┌──────────────┐
│   Zitadel   │  │   OpenFGA    │
│  (Port 8888)│  │  (Port 8889) │
└─────────────┘  └──────────────┘
```

---

## Prerequisites

### Infrastructure Requirements

- **Kubernetes Cluster** (EKS, GKE, AKS) or Docker environment
- **PostgreSQL 14+** for Zitadel and OpenFGA
- **Redis/Valkey** for rate limiting
- **Domain name** with SSL certificate
- **SMTP Server** for email notifications

### Required Accounts/Services

- Container registry (Docker Hub, ECR, GCR)
- Certificate authority (Let's Encrypt, AWS ACM)
- Email delivery service (SendGrid, AWS SES, SMTP provider)

---

## Zitadel Setup

### Step 1: Install Zitadel

#### Option A: Kubernetes (Recommended)

```yaml
# zitadel-deployment.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: zitadel-config
data:
  config.yaml: |
    Log:
      Level: info
    
    Database:
      Postgres:
        Host: postgres.default.svc.cluster.local
        Port: 5432
        Database: zitadel
        User:
          Username: zitadel
          Password: ${DB_PASSWORD}
    
    ExternalDomain: auth.yourdomain.com
    ExternalPort: 443
    ExternalSecure: true
    
    TLS:
      Enabled: false  # Handled by ingress
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: zitadel
spec:
  replicas: 2
  selector:
    matchLabels:
      app: zitadel
  template:
    metadata:
      labels:
        app: zitadel
    spec:
      containers:
      - name: zitadel
        image: ghcr.io/zitadel/zitadel:v2.42.0
        ports:
        - containerPort: 8080
        env:
        - name: DB_PASSWORD
          valueFrom:
            secretKeyRef:
              name: postgres-credentials
              key: password
        volumeMounts:
        - name: config
          mountPath: /config.yaml
          subPath: config.yaml
      volumes:
      - name: config
        configMap:
          name: zitadel-config
---
apiVersion: v1
kind: Service
metadata:
  name: zitadel
spec:
  selector:
    app: zitadel
  ports:
  - port: 8080
    targetPort: 8080
```

#### Option B: Docker Compose

```yaml
version: '3.8'

services:
  zitadel:
    image: ghcr.io/zitadel/zitadel:v2.42.0
    command: 'start-from-init --masterkeyFromEnv --tlsMode disabled'
    environment:
      - ZITADEL_DATABASE_POSTGRES_HOST=postgres
      - ZITADEL_DATABASE_POSTGRES_PORT=5432
      - ZITADEL_DATABASE_POSTGRES_DATABASE=zitadel
      - ZITADEL_DATABASE_POSTGRES_USER_USERNAME=zitadel
      - ZITADEL_DATABASE_POSTGRES_USER_PASSWORD=${DB_PASSWORD}
      - ZITADEL_DATABASE_POSTGRES_ADMIN_USERNAME=postgres
      - ZITADEL_DATABASE_POSTGRES_ADMIN_PASSWORD=${DB_PASSWORD}
      - ZITADEL_EXTERNALDOMAIN=auth.yourdomain.com
      - ZITADEL_EXTERNALPORT=443
      - ZITADEL_EXTERNALSECURE=true
      - ZITADEL_MASTERKEY=${ZITADEL_MASTERKEY}
    ports:
      - "8080:8080"
    depends_on:
      - postgres
```

### Step 2: Configure SSL/TLS

#### Using Kubernetes Ingress + Cert-Manager

```yaml
# ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: zitadel
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - auth.yourdomain.com
    secretName: zitadel-tls
  rules:
  - host: auth.yourdomain.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: zitadel
            port:
              number: 8080
```

**Install cert-manager:**
```bash
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml

# Create ClusterIssuer
cat <<EOF | kubectl apply -f -
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: admin@yourdomain.com
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
    - http01:
        ingress:
          class: nginx
EOF
```

### Step 3: Initial Zitadel Console Login

1. **Access Console**: Navigate to `https://auth.yourdomain.com`
2. **Initial Admin**:
   - Username: `zitadel-admin@zitadel.yourdomain.com`
   - Password: Check deployment logs:
     ```bash
     kubectl logs -l app=zitadel | grep "Initial"
     # Or for Docker:
     docker logs zitadel | grep "Initial"
     ```
3. **Change Password** immediately after first login

### Step 4: Create Organization & Project

#### Create Organization

1. Navigate to **Organizations** → **Create Organization**
2. Fill in:
   - **Name**: Your Company Name
   - **Primary Domain**: `yourdomain.com`
3. Click **Create**

#### Create Project

1. Navigate to **Projects** → **Create Project**
2. Fill in:
   - **Name**: Auth Gateway API
   - **Type**: Application Project
3. Click **Create**

### Step 5: Create OIDC Application

1. In your project, click **New Application**
2. Select **API** (for machine-to-machine)
3. Configure:
   - **Name**: auth-gateway
   - **Auth Method**: Client Secret (Basic)
4. Click **Create**
5. **Save credentials**:
   ```
   Client ID: 123456789@authgateway
   Client Secret: aBcDeFgH... (save securely!)
   ```

### Step 6: Create Service Account (System User)

1. Navigate to **Service Accounts** → **New**
2. Configure:
   - **Username**: gateway-service
   - **Name**: Auth Gateway Service Account
   - **Description**: System account for auth gateway operations
3. Click **Create**
4. **Generate Personal Access Token (PAT)**:
   - Click on the service account
   - Go to **Personal Access Tokens** tab
   - Click **New**
   - Set expiration (e.g., 1 year)
   - **Save the token** (you won't see it again!)

### Step 7: Configure Email/SMTP

1. Navigate to **Settings** → **SMTP**
2. Configure your SMTP provider:

   **Example: AWS SES**
   ```
   Host: email-smtp.us-east-1.amazonaws.com
   Port: 587
   User: SMTP_USERNAME
   Password: SMTP_PASSWORD
   From Address: noreply@yourdomain.com
   From Name: Your Company
   ```

   **Example: SendGrid**
   ```
   Host: smtp.sendgrid.net
   Port: 587
   User: apikey
   Password: SG.xxxxxxx
   From Address: noreply@yourdomain.com
   From Name: Your Company
   ```

3. **Test** by sending a test email

### Step 8: Configure MFA

1. Navigate to **Settings** → **Login** → **Multi-Factor Authentication**
2. Enable desired MFA methods:
   - ✅ **Time-based OTP (TOTP)** - Authenticator apps
   - ✅ **SMS** - Requires SMS provider
   - ✅ **Email OTP** - Uses configured SMTP
3. Set **MFA Policy**:
   - **Mandatory for Admins**: Yes
   - **Mandatory for Users**: Optional (recommend)
4. Click **Save**

### Step 9: Configure Identity Providers (Optional)

If you want to allow users to login with Google, Microsoft, etc.:

#### Add Google IDP

1. Navigate to **Settings** → **Identity Providers** → **New**
2. Select **Google**
3. Configure:
   - **Client ID**: From Google Cloud Console
   - **Client Secret**: From Google Cloud Console
   - **Scopes**: `openid email profile`
4. Click **Add**

#### Add Microsoft/Azure AD

1. Select **Azure AD**
2. Configure:
   - **Client ID**: From Azure Portal
   - **Client Secret**: From Azure Portal
   - **Tenant**: Your Azure AD tenant
3. Click **Add**

### Step 10: Configure Zitadel Actions (Webhooks)

1. Navigate to **Settings** → **Actions**
2. Create **User Created** action:

```javascript
function userCreated(ctx, api) {
  const webhookUrl = 'https://gateway.yourdomain.com/webhooks/user-created';
  
  const payload = {
    userId: ctx.v1.user.id,
    userName: ctx.v1.user.userName,
    userType: ctx.v1.user.type
  };
  
  http.post(webhookUrl, {
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload)
  });
}
```

3. Create **User Deleted** action:

```javascript
function userDeleted(ctx, api) {
  const webhookUrl = 'https://gateway.yourdomain.com/webhooks/user-deleted';
  
  const payload = {
    userId: ctx.v1.deletedUser.id
  };
  
  http.post(webhookUrl, {
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload)
  });
}
```

4. **Attach actions to flows**:
   - Go to **Settings** → **Flows**
   - Find **User Created** flow → Attach `userCreated` action
   - Find **User Deleted** flow → Attach `userDeleted` action

---

## OpenFGA Setup

### Step 1: Deploy OpenFGA

#### Kubernetes Deployment

```yaml
# openfga-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: openfga
spec:
  replicas: 2
  selector:
    matchLabels:
      app: openfga
  template:
    metadata:
      labels:
        app: openfga
    spec:
      containers:
      - name: openfga
        image: openfga/openfga:v1.3.0
        args:
        - run
        ports:
        - containerPort: 8080
        - containerPort: 8081  # gRPC
        - containerPort: 3000  # Playground
        env:
        - name: OPENFGA_DATASTORE_ENGINE
          value: "postgres"
        - name: OPENFGA_DATASTORE_URI
          value: "postgres://openfga:${DB_PASSWORD}@postgres:5432/openfga"
---
apiVersion: v1
kind: Service
metadata:
  name: openfga
spec:
  selector:
    app: openfga
  ports:
  - name: http
    port: 8080
    targetPort: 8080
  - name: grpc
    port: 8081
    targetPort: 8081
```

### Step 2: Create Authorization Model

```bash
# Create store
curl -X POST https://openfga.yourdomain.com/stores \
  -H "Content-Type: application/json" \
  -d '{
    "name": "auth-gateway"
  }'

# Save the store ID from response
export STORE_ID="01HXXX..."

# Create authorization model
curl -X POST https://openfga.yourdomain.com/stores/${STORE_ID}/authorization-models \
  -H "Content-Type": "application/json" \
  -d '{
    "schema_version": "1.1",
    "type_definitions": [
      {
        "type": "user"
      },
      {
        "type": "feature",
        "relations": {
          "viewer": {
            "this": {}
          }
        },
        "metadata": {
          "relations": {
            "viewer": {
              "directly_related_user_types": [
                {"type": "user"}
              ]
            }
          }
        }
      }
    ]
  }'
```

**Save the Store ID** - you'll need it for the auth-gateway configuration.

---

## Auth Gateway Deployment

### Step 1: Build Docker Image

```dockerfile
# Dockerfile (already exists in your project)
FROM rust:1.75-slim as builder
WORKDIR /app
COPY auth-gateway/ .
RUN cargo build --release

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y ca-certificates
COPY --from=builder /app/target/release/auth-gateway /usr/local/bin/
ENTRYPOINT ["auth-gateway"]
```

```bash
# Build
docker build -t your-registry/auth-gateway:v1.0.0 .

# Push
docker push your-registry/auth-gateway:v1.0.0
```

### Step 2: Create Kubernetes Deployment

```yaml
# auth-gateway-deployment.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: access-rules
data:
  access_rules.json: |
    [
      {
        "path": "/api/*path",
        "method": "GET",
        "feature": "feature:report_viewer"
      },
      {
        "path": "/management/v1/*path",
        "method": "*",
        "feature": "public_access",
        "target": "zitadel"
      },
      {
        "path": "/stores/*path",
        "method": "*",
        "feature": "public_access",
        "target": "openfga"
      }
    ]
  access_rules_prev.json: |
    []
---
apiVersion: v1
kind: Secret
metadata:
  name: auth-gateway-secrets
type: Opaque
stringData:
  OPENFGA_STORE_ID: "01HXXX..."
  REDIS_URL: "redis://redis:6379/"
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: auth-gateway
spec:
  replicas: 3
  selector:
    matchLabels:
      app: auth-gateway
  template:
    metadata:
      labels:
        app: auth-gateway
    spec:
      containers:
      - name: auth-gateway
        image: your-registry/auth-gateway:v1.0.0
        ports:
        - containerPort: 3000
        env:
        - name: OPENFGA_URL
          value: "http://openfga:8080"
        - name: OPENFGA_STORE_ID
          valueFrom:
            secretKeyRef:
              name: auth-gateway-secrets
              key: OPENFGA_STORE_ID
        - name: ZITADEL_ISSUER_URL
          value: "https://auth.yourdomain.com"
        - name: ZITADEL_API_URL
          value: "https://auth.yourdomain.com"
        - name: REDIS_URL
          valueFrom:
            secretKeyRef:
              name: auth-gateway-secrets
              key: REDIS_URL
        - name: UPSTREAM_URL
          value: "http://your-app:8080"
        - name: ALLOWED_ORIGINS
          value: "https://app.yourdomain.com"
        volumeMounts:
        - name: access-rules
          mountPath: /app/access_rules.json
          subPath: access_rules.json
        - name: access-rules
          mountPath: /app/access_rules_prev.json
          subPath: access_rules_prev.json
        readinessProbe:
          httpGet:
            path: /health
            port: 3000
          initialDelaySeconds: 5
          periodSeconds: 10
        livenessProbe:
          httpGet:
            path: /health
            port: 3000
          initialDelaySeconds: 15
          periodSeconds: 20
      volumes:
      - name: access-rules
        configMap:
          name: access-rules
---
apiVersion: v1
kind: Service
metadata:
  name: auth-gateway
spec:
  selector:
    app: auth-gateway
  ports:
  - port: 3000
    targetPort: 3000
```

### Step 3: Create Ingress

```yaml
# gateway-ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: auth-gateway
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/rate-limit: "100"
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - gateway.yourdomain.com
    secretName: gateway-tls
  rules:
  - host: gateway.yourdomain.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: auth-gateway
            port:
              number: 3000
```

### Step 4: Deploy

```bash
kubectl apply -f auth-gateway-deployment.yaml
kubectl apply -f gateway-ingress.yaml
```

---

## CI/CD Configuration

### GitHub Actions Example

```yaml
# .github/workflows/deploy-gateway.yml
name: Deploy Auth Gateway

on:
  push:
    branches: [main]
    paths:
      - 'auth-gateway/**'

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      # Build and push image
      - name: Build image
        run: |
          docker build -t ${{ secrets.REGISTRY }}/auth-gateway:${{ github.sha }} .
          docker push ${{ secrets.REGISTRY }}/auth-gateway:${{ github.sha }}
      
      # Backup current access_rules
      - name: Backup access rules
        run: |
          kubectl cp auth-gateway-pod:/app/access_rules.json ./access_rules_prev.json || \
            echo '[]' > access_rules_prev.json
      
      # Update ConfigMap
      - name: Update access rules
        run: |
          kubectl create configmap access-rules \
            --from-file=access_rules.json=auth-gateway/access_rules.json \
            --from-file=access_rules_prev.json=./access_rules_prev.json \
            --dry-run=client -o yaml | kubectl apply -f -
      
      # Update deployment
      - name: Deploy
        run: |
          kubectl set image deployment/auth-gateway \
            auth-gateway=${{ secrets.REGISTRY }}/auth-gateway:${{ github.sha }}
          kubectl rollout status deployment/auth-gateway
```

###GitLab CI Example

```yaml
# .gitlab-ci.yml
stages:
  - build
  - deploy

build:
  stage: build
  script:
    - docker build -t $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA .
    - docker push $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA

deploy:
  stage: deploy
  script:
    # Backup
    - kubectl cp auth-gateway-pod:/app/access_rules.json ./access_rules_prev.json || echo '[]' > access_rules_prev.json
    
    # Update ConfigMap
    - kubectl create configmap access-rules --from-file=access_rules.json --from-file=access_rules_prev.json --dry-run=client -o yaml | kubectl apply -f -
    
    # Deploy
    - kubectl set image deployment/auth-gateway auth-gateway=$CI_REGISTRY_IMAGE:$CI_COMMIT_SHA
    - kubectl rollout status deployment/auth-gateway
  only:
    - main
```

---

## Monitoring & `Maintenance

### Health Checks

Add health endpoint to your app:

```rust
// In main.rs or a separate health module
.route("/health", get(health_check))

async fn health_check() -> &'static str {
    "OK"
}
```

### Prometheus Metrics

Add to deployment:

```yaml
annotations:
  prometheus.io/scrape: "true"
  prometheus.io/port: "3000"
  prometheus.io/path: "/metrics"
```

### Logging

View logs:
```bash
kubectl logs -f -l app=auth-gateway
```

### Backup Strategy

**Zitadel Database**:
```bash
kubectl exec postgres-0 -- pg_dump zitadel > zitadel-backup-$(date +%Y%m%d).sql
```

**OpenFGA Database**:
```bash
kubectl exec postgres-0 -- pg_dump openfga > openfga-backup-$(date +%Y%m%d).sql
```

**Access Rules**:
```bash
kubectl get configmap access-rules -o yaml > access-rules-backup.yaml
```

---

## Troubleshooting

### Common Issues

#### 1. JWT Validation Fails
```
Error: "JWT validation failed"
Solution: Check ZITADEL_ISSUER_URL matches exactly
```

#### 2. OpenFGA Connection Error
```
Error: "Failed to connect to OpenFGA"  
Solution: Verify OPENFGA_STORE_ID and network connectivity
```

#### 3. Rate Limiting Not Working
```
Error: "Rate limiting skipped"
Solution: Ensure Redis is running and REDIS_URL is correct
```

#### 4. Feature Migration Fails
```
Error: "Feature migration failed"
Solution: Check gateway logs, verify both access_rules files exist
```

### Debug Commands

```bash
# Check gateway logs
kubectl logs -l app=auth-gateway --tail=100

# Test JWT validation
curl -H "Authorization: Bearer <token>" https://gateway.yourdomain.com/api/test

# Check OpenFGA connectivity
kubectl exec -it auth-gateway-pod -- curl http://openfga:8080/stores

# Verify Redis
kubectl exec -it redis-pod -- redis-cli ping
```

---

## Security Checklist

- [ ] SSL/TLS certificates configured
- [ ] Rotate service account PATs regularly (every 90 days)
- [ ] Enable MFA for all admin accounts
- [ ] Restrict network access (use security groups/network policies)
- [ ] Regular security updates (keep Zitadel, OpenFGA, gateway updated)
- [ ] Monitor for suspicious activity (failed auth attempts)
- [ ] Backup databases daily
- [ ] Test disaster recovery procedures
- [ ] Review access logs weekly
- [ ] Audit user permissions quarterly

---

## Quick Reference

### Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `OPENFGA_URL` | OpenFGA API endpoint | `http://openfga:8080` |
| `OPENFGA_STORE_ID` | OpenFGA store identifier | `01HXXX...` |
| `ZITADEL_ISSUER_URL` | Zitadel OAuth issuer | `https://auth.yourdomain.com` |
| `ZITADEL_API_URL` | Zitadel API endpoint | `https://auth.yourdomain.com` |
| `REDIS_URL` | Redis connection string | `redis://redis:6379/` |
| `UPSTREAM_URL` | Your application URL | `http://app:8080` |
| `ALLOWED_ORIGINS` | CORS origins | `https://app.yourdomain.com` |

### Useful Commands

```bash
# Restart gateway
kubectl rollout restart deployment/auth-gateway

# Scale replicas
kubectl scale deployment/auth-gateway --replicas=5

# View secrets
kubectl get secret auth-gateway-secrets -o yaml

# Update access rules
kubectl edit configmap access-rules

# Check certificate expiry
kubectl get certificate
```

---

## Support & References

- [Zitadel Documentation](https://zitadel.com/docs)
- [OpenFGA Documentation](https://openfga.dev/docs)
- [Feature Sync Guide](file:///home/ubuntu/performant_python/FEATURE_SYNC.md)
- [Webhook Integration](file:///home/ubuntu/performant_python/ZITADEL_WEBHOOK_INTEGRATION.md)
