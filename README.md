# Cerevyn Technical Assessment - PS04: Azure Support Ticket Automation

**Assessment Track:** AI Automation with Azure Implementation  
**Problem ID:** PS04 (Azure Support Ticket Automation)  
**Candidate Name:** Tejas Gupta 
**Roll Number:** 2310991230  
**Branch:** CSE 
**Repository Branch:** `main`

---

## 1. Problem Statement Overview

Support teams spend significant manual effort reading tickets, categorizing issues, determining priority, and routing them to specialized teams.

This project delivers an end-to-end AI-assisted automation service that:
1. Ingests customer support queries through a secure REST API.
2. Automatically classifies tickets into four functional domains: **Billing**, **Technical**, **Access**, and **General**.
3. Enforces an explicit, documented **Priority Policy** (`Critical`, `High`, `Medium`, `Low`) based on business criticality and SLA impact.
4. Synthesizes a concise summary and prepares a context-aware **draft response**.
5. Employs **uncertainty and ambiguity detection** to flag low-confidence tickets for mandatory human triage.
6. Rejects duplicate ticket IDs (HTTP 409) and invalid payloads (HTTP 422).
7. Enforces a **Human-in-the-Loop Approval Gateway** where drafts require approval before dispatch, maintaining an immutable audit log.
8. Evaluates and reports classification accuracy on a reserved 10-ticket test set (90% accuracy).
9. Comes packaged with a production **Dockerfile**, **GitHub Actions CI/CD workflows** with OIDC federation, an interactive evaluation web dashboard, and an Azure cloud architecture specification.

---

## 2. System Architecture & Components

- **API Framework:** FastAPI (Python 3.12) with Pydantic v2 schemas and CORS support.
- **NLP & Classification Engine:** Scikit-Learn TF-IDF N-gram feature extraction paired with Logistic Regression (multiclass with probability calibration).
- **Priority Policy Engine:** Deterministic rule and SLA matcher analyzing service disruption, financial impact, and account security.
- **Data Persistence & Audit Trail:** ACID-compliant SQLite layer tracking ticket state (`pending_review`, `approved`, `rejected`) and timestamped reviewer action logs.
- **Interactive UI Dashboard:** Built-in web UI served directly at `http://localhost:8000/` for evaluation and demonstration.
- **Containerization:** Multi-stage production `Dockerfile` with health probes.
- **CI/CD:** GitHub Actions test workflow (`.github/workflows/ci.yml`) and Azure App Service OIDC deployment workflow (`.github/workflows/azure-deploy.yml`).

---

## 3. Priority Policy & Team Routing Policy

### Priority Policy
- **Critical:** Systemic production outages, service unavailability (HTTP 500/503), core checkout blockers.
- **High:** Financial discrepancies (double charges, unauthorized debits), account suspensions, security admin lockouts, SSL handshake failures.
- **Medium:** Standard technical bugs (CSV crashes, query bugs), VAT/invoice downloads, SSO/SAML provisioning, password reset issues.
- **Low:** Cosmetic issues, dark mode UI bugs, GDPR compliance questions, sales demo inquiries, feature suggestions.

### Team Routing Mapping
- **Billing** &rarr; *Finance & Billing Ops Team*
- **Technical** &rarr; *Tier-2 Technical Support & Engineering*
- **Access** &rarr; *Identity & Access Management (IAM) Team*
- **General** &rarr; *Customer Success & Information Desk*

---

## 4. Setup and Run Instructions

### Prerequisites
- Python 3.10+ (tested on Python 3.12)
- Git
- Docker (optional for containerized run)

### Local Setup
1. **Clone the repository:**
   ```bash
   git clone <repo-url>
   cd Cerevyn-Chitkara-RollNumber-PS04
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the API server:**
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

5. **Access Application Endpoints:**
   - **Interactive Web Dashboard:** [http://localhost:8000/](http://localhost:8000/)
   - **Interactive Swagger Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
   - **Health Check:** [http://localhost:8000/health](http://localhost:8000/health)
   - **Accuracy Evaluation Metric:** [http://localhost:8000/metrics/accuracy](http://localhost:8000/metrics/accuracy)

---

## 5. Automated Testing

Run the full automated test suite covering all 6 assessment scenarios:
```bash
python -m pytest tests/ -v
```

### Test Scenarios Covered
1. `test_health_check`: Verifies server health and classifier initialization.
2. `test_normal_ticket_creation_and_routing`: Validates category prediction, priority assignment, and assigned team.
3. `test_critical_outage_priority_policy`: Validates that production-down events trigger Critical priority.
4. `test_ambiguous_ticket_routes_to_review`: Validates ambiguity detection and review flag routing.
5. `test_duplicate_ticket_id_rejection`: Validates duplicate ticket ID rejection with HTTP 409.
6. `test_invalid_input_validation`: Validates input length constraints and Pydantic validation (HTTP 422).
7. `test_human_approval_workflow_and_audit_trail`: Validates human sign-off state change and immutable audit log preservation.
8. `test_test_set_accuracy_metric`: Evaluates prediction accuracy against reserved test set (&ge; 80%).

---

## 6. Docker Container Execution

### Build Docker Image
```bash
docker build -t cerevyn-ticket-automation:latest .
```

### Run Container Locally
```bash
docker run -d -p 8000:8000 --name cerevyn-service cerevyn-ticket-automation:latest
```

Verify container operation:
```bash
curl http://localhost:8000/health
```

---

## 7. Model Evaluation & Accuracy Report

The model is trained on 20 balanced multi-class support tickets and evaluated on **10 unseen reserved test tickets** spanning all 4 categories (`Billing`, `Technical`, `Access`, `General`):

- **Total Test Samples:** 10
- **Correct Predictions:** 9 / 10
- **Observed Accuracy:** **90.0%**
- **Category Breakdown:**
  - `Billing`: 2 / 2 (100%)
  - `Technical`: 3 / 3 (100%)
  - `Access`: 2 / 2 (100%)
  - `General`: 2 / 3 (66.7%)

Uncertainty routing activates when prediction confidence is below 0.45 or when the difference between the top two candidate classes is under 0.25, ensuring that edge cases are safely held for human oversight.

---

## 8. Demonstration Scenarios Guide (For Reviewers)

| Test Case | Method | Endpoint | Sample Payload | Expected Output |
| :--- | :--- | :--- | :--- | :--- |
| **Category Assignment** | `POST` | `/tickets` | `{"ticket_id":"T-1","message":"My corporate card was double billed."}` | Category: `Billing`, Priority: `High`, Status: `pending_review` |
| **Ambiguous Ticket** | `POST` | `/tickets` | `{"ticket_id":"T-2","message":"help please urgently system error broken"}` | `needs_review: true`, `review_reason` populated |
| **Duplicate ID** | `POST` | `/tickets` | `{"ticket_id":"T-1", ...}` | `409 Conflict: Ticket 'T-1' already exists` |
| **Invalid Input** | `POST` | `/tickets` | `{"ticket_id":"", "message":"hi"}` | `422 Unprocessable Entity` |
| **Human Approval** | `POST` | `/tickets/T-1/approve` | `{"decision":"approved","reviewer_name":"Lead Admin"}` | Status transitions to `approved`, audit log recorded |
| **Audit Log Trail** | `GET` | `/tickets/T-1/audit` | N/A | Full history of actions and timestamps |

---

## 9. Azure Deployment Plan Reference

A detailed Azure enterprise deployment plan is documented in [`docs/azure-plan.md`](docs/azure-plan.md), including:
- Azure App Service on Linux Container configuration.
- Passwordless GitHub Actions CI/CD via **OIDC Federated Credentials**.
- Azure Key Vault & Managed Identity secret management.
- Application Insights telemetry and cost-control recommendations.

---

## 10. Limitations & Future Roadmap

1. **Dataset Scale:** Current lightweight TF-IDF model is trained on 20 carefully curated seed samples. Future iterations can integrate transformer embeddings (e.g. `all-MiniLM-L6-v2` or Azure OpenAI Service).
2. **Persistence:** Local development uses SQLite; production deployment maps to Azure Database for PostgreSQL Flexible Server.
3. **Multi-language Support:** Current NLP processing is optimized for English queries; future enhancement will support multilingual ticket translation.
