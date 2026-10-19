# 3 to 5-Minute Video Demonstration Script & Guide
## PS04: Azure Support Ticket Automation (Cerevyn Technical Assessment)

This script is structured to ensure you cover **all criteria from the 100-mark evaluation rubric** within 3 to 5 minutes.

---

### Recommended Recording Setup
- **Tool**: Loom, OBS Studio, or Windows Xbox Game Bar (`Win + G`).
- **Screen**: Full screen browser showing [http://127.0.0.1:8000/](http://127.0.0.1:8000/).
- **Have open in background tabs**:
  1. [http://127.0.0.1:8000/](http://127.0.0.1:8000/) (Interactive Dashboard)
  2. [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) (Swagger API Docs)
  3. VS Code / Terminal (to show `python -m pytest tests/ -v`)
  4. GitHub Repository: [https://github.com/Tejasgupta74/ai-automated-ticket-system](https://github.com/Tejasgupta74/ai-automated-ticket-system)

---

### Step-by-Step Walkthrough (Minute-by-Minute)

#### Minute 0:00 - 0:45 | Introduction & Problem Overview
> *"Hello! This is the demonstration of my submission for the Cerevyn Technical Assessment — Problem Statement PS04: Azure Support Ticket Automation.*
>
> *Our goal is to build an intelligent, production-ready backend service and dashboard that automatically ingests incoming customer tickets, classifies them into four categories — Billing, Technical, Access, and General — enforces explicit SLA priority policies, flags uncertain cases for human triage, and maintains an immutable audit trail before responses are approved."*

---

#### Minute 0:45 - 1:45 | Scenario 1: Normal Ingestion & Priority Policy (Critical vs. Billing)
1. **Show the UI Dashboard** at [http://127.0.0.1:8000/](http://127.0.0.1:8000/).
2. **Click the "Critical Outage" demo button**:
   - Notice the ticket ID is auto-generated (or custom).
   - Message: *"Production database timeout throwing 500 internal server error for all web clients!"*
   - Click **"Classify & Ingest Ticket"**.
   - Show the result in the right-hand panel:
     - **Category**: `Technical`
     - **Priority**: `Critical` (Explain: *"Systemic production outages immediately trigger the Critical SLA policy."*)
     - **Assigned Team**: `Tier-2 Technical Support & Engineering`
     - **Draft Response**: Tailored engineering response ready for human sign-off.
3. **Click the "Double Charge" demo button**:
   - Message: *"I was double charged on my credit card for the monthly subscription invoice #99283."*
   - Click **"Classify & Ingest Ticket"**.
   - Show the result:
     - **Category**: `Billing`
     - **Priority**: `High`
     - **Assigned Team**: `Finance & Billing Ops Team`

---

#### Minute 1:45 - 2:30 | Scenario 2: Ambiguity Detection & Human Triage
1. **Click the "Ambiguous Inquiry" demo button**:
   - Message: *"help please urgently system error broken"*
   - Click **"Classify & Ingest Ticket"**.
   - Point out the red badge:
     - **Triage**: `Needs Review`
     - Explain: *"When the model's confidence is below threshold or when the margin between candidate classes is close, the system automatically routes the ticket to human review rather than guessing, fulfilling the assessment's reliability requirement."*

---

#### Minute 2:30 - 3:15 | Scenario 3: Human Approval Workflow & Immutable Audit Trail
1. In the active tickets queue, click **"Inspect"** on any pending ticket.
2. Click **"Approve Draft Response"**:
   - Enter reviewer name: e.g. `Senior Support Lead`.
   - Enter notes: e.g. `Draft response validated and approved for dispatch.`
3. Show the updated state:
   - Status changes from `pending_review` to `approved`.
   - Scroll down to show the **Immutable Audit Trail**:
     - `CREATED` event with timestamp.
     - `STATUS_CHANGE_APPROVED` event with timestamp, reviewer name, and notes.

---

#### Minute 3:15 - 3:50 | Scenario 4: Accuracy Metrics & 10 Reserved Test Set
1. Click the **"Check Model Accuracy"** button in the header.
2. Show the live evaluation box:
   - Total test samples: 10
   - Correct predictions: 9
   - **Observed Accuracy: 90.0%**
   - Explain: *"The assessment required reserving at least 10 tickets as an unseen test set. Here we demonstrate 90% accuracy across all four categories."*

---

#### Minute 3:50 - 4:30 | Scenario 5: Automated Tests & Cloud Architecture
1. **Switch to terminal** and run:
   ```bash
   python -m pytest tests/ -v
   ```
   - Show all **11 automated tests passing** (covering normal routing, outage priority, ambiguity, duplicate rejection, invalid input validation, approval audit trail, and accuracy).
2. **Briefly show GitHub Repository & Azure Plan**:
   - Show `.github/workflows/ci.yml` (automated CI pipeline).
   - Show `docs/azure-plan.md` (covering App Service Linux container hosting, Entra ID OIDC passwordless authentication, Key Vault secret management, and cost-control sizing).

---

#### Minute 4:30 - 4:45 | Conclusion
> *"In summary, the solution meets all functional requirements, provides complete test coverage, error handling, Docker containerization, and is ready for Azure App Service deployment. Thank you!"*
