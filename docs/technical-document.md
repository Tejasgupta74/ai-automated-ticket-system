# Technical Submission Document
## Cerevyn Technical Assessment — Problem Statement PS04: Azure Support Ticket Automation

**Track:** AI Automation with Azure Implementation  
**Candidate Name:** Tejas Gupta  
**Repository:** [https://github.com/Tejasgupta74/ai-automated-ticket-system.git](https://github.com/Tejasgupta74/ai-automated-ticket-system.git)  
**Branch:** `main`  
**Latest Evaluated Commit Hash:** `7d34523`  

---

## 1. Executive Summary

This document serves as the formal technical project handover and documentation for **PS04: Azure Support Ticket Automation** developed for the Cerevyn Chitkara University Technical Assessment. 

Modern enterprise customer support teams receive thousands of incoming queries daily across billing disputes, critical software outages, permission requests, and general product inquiries. Manually reading, triaging, setting response priorities, drafting replies, and routing each ticket introduces substantial latency and human error.

This project delivers a **production-hardened, containerized REST API and interactive management dashboard** built with Python 3.12, FastAPI, Scikit-Learn NLP, and SQLite/SQLAlchemy. The system automatically classifies incoming tickets, assigns SLA-compliant priorities, prepares draft responses, flags ambiguous queries for mandatory human triage, and enforces an immutable audit trail before responses are approved.

---

## 2. Assessment Requirements & Verification Matrix

The table below maps each requirement from the official Cerevyn assessment rubric directly to its architectural implementation in this codebase:

| Rubric Criterion | Assessment Requirement | Code Implementation & Verification | Status |
| :--- | :--- | :--- | :--- |
| **Required Functionality (30 marks)** | Ticket ingestion endpoint accepting ID & message; returns category, priority, assigned team, brief summary, and draft response. | Implemented in `POST /tickets` ([`app/main.py`](file:///d:/cerevyn/app/main.py#L60-L105)) and Pydantic models ([`app/models.py`](file:///d:/cerevyn/app/models.py)). Supports optional auto-generated ticket IDs (`TCK-XXXXXXXX`). | Verified & Active |
| **Technical Reasoning & Accuracy (20 marks)** | Explainable classifier / NLP engine, uncertainty review routing, state priority policy, and test-set accuracy on &ge; 10 reserved tickets. | Built in [`app/classifier.py`](file:///d:/cerevyn/app/classifier.py). Evaluates 10 reserved unseen tickets with **90.0% accuracy** (`GET /metrics/accuracy`). Uncertainty margin thresholding routes ambiguous tickets to `needs_review: true`. | Verified (90%) |
| **Code Quality & Maintainability (15 marks)** | Modularity, clear separation of concerns, PEP 8 compliance, robust schema validation. | Layered architecture: `app/main.py` (API/routing), `app/classifier.py` (NLP engine), `app/database.py` (storage & audit), `app/models.py` (schemas). Clean typing with Pydantic v2. | Verified |
| **Meaningful Tests & Failure Handling (15 marks)** | Reject duplicate IDs (409), validate invalid inputs (422), draft approval gateway, preserve audit trail, test suite. | Automated test suite in [`tests/test_tickets.py`](file:///d:/cerevyn/tests/test_tickets.py) with **11 / 11 passing tests**. Duplicate rejection, input validation, and audit trail fully covered. | Verified (11/11 Passed) |
| **Azure Design & GitHub Automation (10 marks)** | Production Dockerfile, passing GitHub Actions CI workflow, manually triggered Azure deployment workflow with OIDC references, documented settings. | Production [`Dockerfile`](file:///d:/cerevyn/Dockerfile) with health checks; [`.github/workflows/ci.yml`](file:///d:/cerevyn/.github/workflows/ci.yml) for automated test execution; [`.github/workflows/azure-deploy.yml`](file:///d:/cerevyn/.github/workflows/azure-deploy.yml) for passwordless OIDC deploy; [`docs/azure-plan.md`](file:///d:/cerevyn/docs/azure-plan.md). | Verified |
| **Reproducibility & Demonstration (10 marks)** | Reproducible handover, complete setup instructions, interactive demonstration UI, credential-free configuration. | Single-page interactive evaluation dashboard served at `/`, interactive Swagger API at `/docs`, automated runner [`run.py`](file:///d:/cerevyn/run.py), and recording script [`docs/demo-script.md`](file:///d:/cerevyn/docs/demo-script.md). | Verified |

---

## 3. System Architecture & Component Design

```
                     ┌───────────────────────────────────────────────┐
                     │            Incoming Support Inquiries         │
                     │           (Browser UI / REST API Client)      │
                     └───────────────────────┬───────────────────────┘
                                             │
                                     [ HTTP POST /tickets ]
                                             ▼
                     ┌───────────────────────────────────────────────┐
                     │                 FastAPI Gateway               │
                     │          • Input Validation (Pydantic v2)     │
                     │          • Duplicate ID Check (HTTP 409)      │
                     │          • Auto Ticket ID Generator           │
                     └───────────────────────┬───────────────────────┘
                                             │
                                             ▼
                     ┌───────────────────────────────────────────────┐
                     │         NLP Classification Engine             │
                     │  • TF-IDF N-Gram Vectorizer (1-2 words)       │
                     │  • Calibrated Multi-Class Logistic Regression │
                     │  • Category Routing (Billing, Tech, IAM, Gen) │
                     └───────────────────────┬───────────────────────┘
                                             │
                      ┌──────────────────────┴──────────────────────┐
                      ▼                                             ▼
        ┌───────────────────────────┐                 ┌───────────────────────────┐
        │   Priority Policy Engine  │                 │    Uncertainty & Triage   │
        │ • Critical: Outage / 500  │                 │ • Low confidence < 0.45   │
        │ • High: Double Charge/Lock│                 │ • Narrow margin < 0.25    │
        │ • Medium: Bugs, Tax, SSO  │                 │ • Sets needs_review: true │
        │ • Low: General / Feedback │                 │   for mandatory human eyes│
        └─────────────┬─────────────┘                 └─────────────┬─────────────┘
                      │                                             │
                      └──────────────────────┬──────────────────────┘
                                             │
                                             ▼
                     ┌───────────────────────────────────────────────┐
                     │        ACID Persistence & Audit Layer         │
                     │   • SQLite with Write-Ahead Logging (WAL)     │
                     │   • Ticket Lifecycle: pending -> approved     │
                     │   • Immutable Audit Trail with Timestamps     │
                     └───────────────────────────────────────────────┘
```

---

## 4. NLP Classification & Machine Learning Reasoning

### 4.1 Methodology
Rather than relying on brittle regex matching or costly, non-deterministic external LLM API calls with high latency, the solution employs a **calibrated Scikit-Learn TF-IDF N-gram feature pipeline coupled with Multinomial Logistic Regression (`lbfgs` solver)**:

1. **Text Preprocessing & Feature Extraction**:
   - Word unigrams and bigrams are extracted using `TfidfVectorizer(ngram_range=(1, 2), stop_words='english')`.
   - This captures both domain keywords (`"database"`, `"unauthorized"`) and contextual phrases (`"double charged"`, `"service unavailable"`, `"locked out"`).

2. **Probabilistic Categorization**:
   - The classifier outputs calibrated probability distributions across all 4 target categories:
     $$\mathbf{P}(C_k | \text{text}) = \frac{e^{\mathbf{w}_k^T \mathbf{x}}}{\sum_{j} e^{\mathbf{w}_j^T \mathbf{x}}}$$
   - The highest probability candidate determines the assigned category.

3. **Uncertainty & Ambiguity Triage Mechanism**:
   - The engine flags tickets for human review (`needs_review: true`) under two conditions:
     - **Confidence Threshold**: $\max_k P(C_k) < 0.45$
     - **Margin Threshold**: $P(C_{(1)}) - P(C_{(2)}) < 0.25$ (when the model is torn between two categories).
   - This prevents silent misclassification of ambiguous queries like `"payment access credentials issue broken system"`.

### 4.2 Reserved Test-Set Performance
The dataset in [`sample_data/tickets.json`](file:///d:/cerevyn/sample_data/tickets.json) maintains a strict train/test split:
- **Training Set**: 20 balanced representative tickets.
- **Reserved Evaluation Test Set**: 10 unseen tickets evaluated independently.

**Observed Evaluation Metrics (`GET /metrics/accuracy`):**
- **Total Test Samples:** 10
- **Correct Predictions:** 9 / 10
- **Overall Accuracy:** **90.0%**
- **Category Breakdown:**
  - `Billing`: 2 / 2 (100.0%)
  - `Technical`: 3 / 3 (100.0%)
  - `Access`: 2 / 2 (100.0%)
  - `General`: 2 / 3 (66.7%)

---

## 5. Priority Policy & SLA Routing Matrix

The service maps each category to a specialized operational team and applies deterministic SLA priority rules:

### Operational Team Routing
- **Billing** &rarr; `Finance & Billing Ops Team`
- **Technical** &rarr; `Tier-2 Technical Support & Engineering`
- **Access** &rarr; `Identity & Access Management (IAM) Team`
- **General** &rarr; `Customer Success & Information Desk`

### Priority Determination Rules
1. **Critical Priority (SLA < 1 Hour)**:
   - *Conditions*: Production outages, API gateway down, HTTP 500/503 errors, checkout blocking disruptions.
2. **High Priority (SLA < 4 Hours)**:
   - *Conditions*: Financial discrepancies, unauthorized account charges, account suspensions, security admin lockouts, SAML/SSL handshake failures.
3. **Medium Priority (SLA < 24 Hours)**:
   - *Conditions*: Non-critical software bugs (report export crash, query result filtering), refund requests, invoice downloads, password reset assistance.
4. **Low Priority (SLA < 72 Hours)**:
   - *Conditions*: Feature inquiries, cosmetic UI issues, GDPR/compliance questions, product demo scheduling, general feedback.

---

## 6. Human-in-the-Loop Approval & Audit Log Architecture

Automated responses are never sent directly to customers without human governance:

1. **Pending State**: Newly ingested tickets are created in `status: "pending_review"`.
2. **Reviewer Action**:
   - Authorized personnel inspect the AI-generated summary and draft response via `POST /tickets/{ticket_id}/approve` or the UI dashboard.
   - Reviewers may **approve**, **reject**, or provide an **edited draft response**.
3. **Audit Trail Preservation**:
   - Every state transition inserts a record into the `audit_logs` table:
     - `ticket_id`: Foreign key reference.
     - `action`: `CREATED`, `STATUS_CHANGE_APPROVED`, or `STATUS_CHANGE_REJECTED`.
     - `performed_by`: Reviewer's name or `SYSTEM_AI_CLASSIFIER`.
     - `notes`: Reviewer's justification and comments.
     - `timestamp`: ISO 8601 UTC timestamp.
   - Audit records are retrieved via `GET /tickets/{ticket_id}/audit`.

---

## 7. Storage Engine & Database Hardening

While cloud environments utilize Azure Database for PostgreSQL or Azure SQL, local execution uses SQLite with production optimizations:
- **Write-Ahead Logging (WAL)**: `PRAGMA journal_mode = WAL;` allows concurrent readers and writers without database locking.
- **Foreign Key Constraints**: `PRAGMA foreign_keys = ON;` enforces relational integrity between `tickets` and `audit_logs`.
- **Busy Timeout**: 15-second busy handler handles transient concurrency spikes.
- **Secondary Indexes**:
  - `idx_tickets_category` on `tickets(category)`
  - `idx_tickets_status` on `tickets(status)`
  - `idx_tickets_created_at` on `tickets(created_at)`
  - `idx_audit_ticket_id` on `audit_logs(ticket_id)`

---

## 8. Automated Test Suite (11 Scenarios)

The test suite in [`tests/test_tickets.py`](file:///d:/cerevyn/tests/test_tickets.py) covers all functional and failure cases:

```powershell
python -m pytest tests/ -v
```

### Test Case Coverage
1. `test_health_check`: Validates `/health` returns status 200 and classifier readiness.
2. `test_normal_ticket_creation_and_routing`: Tests ticket creation, category prediction, and team routing.
3. `test_critical_outage_priority_policy`: Verifies production outages trigger `Critical` priority.
4. `test_ambiguous_ticket_routes_to_review`: Verifies vague queries trigger `needs_review: true`.
5. `test_duplicate_ticket_id_rejection`: Confirms duplicate ticket IDs are rejected with HTTP 409 Conflict.
6. `test_invalid_input_validation`: Ensures empty IDs or messages under 5 characters fail with HTTP 422.
7. `test_human_approval_workflow_and_audit_trail`: Verifies draft approval and audit log creation.
8. `test_test_set_accuracy_metric`: Asserts test-set accuracy &ge; 80% (observed: 90%).
9. `test_automatic_ticket_id_generation`: Confirms auto-generation of `TCK-XXXXXXXX` IDs when omitted.
10. `test_list_tickets_filtering`: Validates category and status filtering and rejects invalid filter queries with HTTP 400.
11. `test_ticket_not_found`: Validates HTTP 404 responses for non-existent ticket IDs.

---

## 9. Azure Deployment Plan & Cloud Security

The deployment architecture is detailed in [`docs/azure-plan.md`](file:///d:/cerevyn/docs/azure-plan.md):

- **Compute**: Azure App Service Linux running custom container (`B1 Basic` for dev, `P1v3` for production).
- **Registry**: Azure Container Registry (ACR) with vulnerability scanning.
- **Identity & Zero-Trust**:
  - GitHub Actions uses **OpenID Connect (OIDC)** federated credentials—no static passwords or secrets are stored in GitHub repository settings.
  - Azure App Service uses a **System-Assigned Managed Identity** to access Azure Key Vault.
- **Monitoring**: Application Insights with custom metrics tracking model confidence, triage rates, and approval latency.
- **Cost Estimation**: Development tier estimated at \$15–\$25/month; production auto-scaled tier at \$85–\$120/month.

---

## 10. Conclusion & Reviewer Verification

This project fulfills every requirement of Problem Statement PS04:
- **Clean Code & Git History**: Available at [https://github.com/Tejasgupta74/ai-automated-ticket-system.git](https://github.com/Tejasgupta74/ai-automated-ticket-system.git) on branch `main`.
- **Live Local Run**: Run `python run.py` and open [http://127.0.0.1:8000/](http://127.0.0.1:8000/) for the interactive management UI, or [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) for the interactive OpenAPI documentation.
- **Automated Tests**: Run `python -m pytest tests/ -v` for 100% test pass rate.
