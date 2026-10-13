# Azure Deployment & Architecture Plan: PS04 Azure Support Ticket Automation

## 1. Executive Summary & Architecture Overview

The **Cerevyn Azure Support Ticket Automation** service is engineered as a containerized, cloud-ready REST API and reasoning engine. It ingests customer queries, performs automated categorization via Scikit-Learn NLP, applies explicit SLA priority policies, flags ambiguous inquiries for human review, and maintains a strict audit trail before drafts are approved.

```
                              ┌───────────────────────────────────────────────┐
                              │             Azure Cloud Architecture          │
                              └───────────────────────────────────────────────┘
                                                      │
                                           [ HTTPS / TLS 1.3 ]
                                                      ▼
                                       ┌─────────────────────────────┐
                                       │    Azure Front Door / AGW   │
                                       │  (WAF & SSL Termination)    │
                                       └──────────────┬──────────────┘
                                                      │
                                                      ▼
                                       ┌─────────────────────────────┐
                                       │   Azure App Service Linux   │
                                       │     (Custom Container)      │
                                       │  ┌───────────────────────┐  │
                                       │  │ FastAPI Ingestion API │  │
                                       │  │ NLP Classifier Engine │  │
                                       │  │ Human Approval Portal │  │
                                       │  └───────────┬───────────┘  │
                                       └──────────────┼──────────────┘
                                                      │
                       ┌──────────────────────────────┴──────────────────────────────┐
                       │                                                             │
                       ▼                                                             ▼
         ┌───────────────────────────┐                                 ┌───────────────────────────┐
         │ Azure SQL / Cosmos DB     │                                 │   Azure Monitor &         │
         │ (Ticket State & Audit Log)│                                 │   Application Insights    │
         └───────────────────────────┘                                 └───────────────────────────┘
```

---

## 2. Azure Compute & Storage Choices

| Component | Selected Azure Resource | SKU / Tier (Cost-Optimized) | Justification |
| :--- | :--- | :--- | :--- |
| **Compute** | **Azure App Service (Linux)** | **B1 Basic** (dev) / **P1v3** (prod) | Native Docker container hosting, continuous zero-downtime deployment slots, automated TLS certificate provisioning, built-in health probes. |
| **Container Registry**| **Azure Container Registry (ACR)** | **Basic** | Private, secure OCI-compliant image storage with tight integration into GitHub Actions. |
| **Relational / State Storage** | **Azure Database for PostgreSQL Flexible Server** or **Azure SQL Database** | **Standard S0 / Burstable B1ms** | Relational integrity for tickets, foreign-key linked audit logs, ACID compliance, point-in-time restore. (Local environment uses embedded SQLite). |
| **Blob / Evidence Storage** | **Azure Blob Storage** | **Standard Hot** | Storing customer attachments, logs, and compliance export reports. |
| **Secrets Management** | **Azure Key Vault** | **Standard** | Centralized storage of API keys, connection strings, and certificates. |

---

## 3. Identity and Secret Handling (Zero Trust & OIDC)

1. **Passwordless GitHub Actions CI/CD via OIDC (OpenID Connect)**:
   - No permanent Azure service principal passwords or client secrets are stored in GitHub repository secrets.
   - GitHub Actions assumes an Azure Entra ID (formerly Azure AD) App Registration using federated credentials scoped strictly to the `main` branch and environment.
2. **Managed Identities for Azure Resources**:
   - The App Service runs with a **System-Assigned Managed Identity**.
   - Grants fine-grained RBAC permissions:
     - `Key Vault Secrets User` on Azure Key Vault.
     - `AcrPull` on Azure Container Registry.
     - `SQL DB Contributor` on database resources.
3. **Application Settings (`.env` & App Settings)**:
   - Key Vault secret references (`@Microsoft.KeyVault(...)`) populate environment variables directly into the container runtime without manual credential exposure.

---

## 4. Monitoring, Observability, and Health Checks

1. **Application Insights & Azure Monitor**:
   - Distributed telemetry tracking response latency, throughput, error rates, and failure dependencies.
   - Custom metric telemetry: Track `model_prediction_confidence`, `ambiguous_ticket_count`, and `approval_latency_seconds`.
2. **Health Probe**:
   - Azure App Service configured with `/health` liveness probe.
   - Verifies API responsiveness and that classifier models are loaded in memory.
3. **Alerting Rules**:
   - Alert on HTTP 5xx rate > 1% over 5-minute window.
   - Alert on queue of unreviewed tickets exceeding 50 pending records.

---

## 5. Deployment Steps (GitHub Actions & Azure CLI)

### Step 1: Provision Core Infrastructure (Azure CLI)
```bash
# 1. Create Resource Group
az group create --name rg-cerevyn-ps04 --location eastus

# 2. Create Azure Container Registry
az acr create --resource-group rg-cerevyn-ps04 --name cerevynacr --sku Basic --admin-enabled false

# 3. Create App Service Plan (Linux)
az appservice plan create --name plan-cerevyn --resource-group rg-cerevyn-ps04 --is-linux --sku B1

# 4. Create Web App for Containers
az webapp create --resource-group rg-cerevyn-ps04 --plan plan-cerevyn --name cerevyn-ps04-ticket-service \
  --deployment-container-image-name cerevynacr.azurecr.io/ticket-automation:latest
```

### Step 2: Configure Entra ID OIDC Federated Credential
```bash
# Create App Registration for GitHub Actions OIDC
az ad app create --display-name github-actions-cerevyn
# Attach federated identity credential linked to repository repository:org/repo:ref:refs/heads/main
```

### Step 3: Trigger GitHub Actions Deployment
- Trigger `.github/workflows/azure-deploy.yml` from GitHub Actions UI or push to `main`.
- The container builds, passes automated tests, pushes to ACR, and updates the App Service container revision.

---

## 6. Cost-Control Assumptions & Sizing

| Environment | Monthly Budget Estimate | Optimization Levers Applied |
| :--- | :--- | :--- |
| **Development & Test** | ~\$15 – \$25 / month | • App Service B1 tier with automatic shutdown outside working hours.<br>• SQLite / Local storage for dev workloads.<br>• Basic ACR. |
| **Production Baseline** | ~\$85 – \$120 / month | • App Service P1v3 with auto-scale (1–3 instances on CPU > 75%).<br>• Azure SQL Burstable B1ms.<br>• Reserved instances for compute savings (up to 38% reduction). |
| **Serverless Alternative** | ~\$5 – \$10 / month | • Azure Container Apps (Scale to zero when idle). Ideal for erratic ticket volume. |
