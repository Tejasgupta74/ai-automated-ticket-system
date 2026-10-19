"""
Comprehensive automated tests covering normal behavior, error cases, and assessment requirements.
Scenarios:
1. Category and priority assignment (Normal flow)
2. Handling ambiguous / uncertain tickets (Review routing)
3. Duplicate ticket ID rejection (409 Conflict)
4. Invalid input validation (Pydantic 422 Unprocessable Entity)
5. Human approval workflow and audit log preservation
6. Model accuracy evaluation against reserved test set
"""

import pytest
import os
import tempfile
from fastapi.testclient import TestClient

# Use temporary DB for tests
test_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
test_db.close()
os.environ["SQLITE_DB_PATH"] = test_db.name

from app.main import app
from app.database import init_db

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_database():
    init_db()
    yield


def test_health_check():
    """Verify health endpoint returns status 200 and healthy status."""
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["classifier_ready"] is True


def test_normal_ticket_creation_and_routing():
    """Scenario 1: Normal ticket submission, priority policy, and team assignment."""
    payload = {
        "ticket_id": "TICK-TEST-101",
        "message": "I was double charged on my corporate credit card for invoice #49281."
    }
    res = client.post("/tickets", json=payload)
    assert res.status_code == 201
    data = res.json()
    
    assert data["ticket_id"] == "TICK-TEST-101"
    assert data["category"] == "Billing"
    assert data["priority"] == "High"
    assert "Finance & Billing Ops Team" in data["assigned_team"]
    assert data["status"] == "pending_review"
    assert len(data["draft_response"]) > 20


def test_critical_outage_priority_policy():
    """Verify production outage triggers Critical priority."""
    payload = {
        "ticket_id": "TICK-TEST-CRIT",
        "message": "Production outage: API gateway completely down with recurring 500 error crashing production!"
    }
    res = client.post("/tickets", json=payload)
    assert res.status_code == 201
    data = res.json()
    
    assert data["category"] == "Technical"
    assert data["priority"] == "Critical"
    assert "Tier-2 Technical Support & Engineering" in data["assigned_team"]


def test_ambiguous_ticket_routes_to_review():
    """Scenario 2: Low-confidence / vague ticket is flagged with needs_review=True."""
    payload = {
        "ticket_id": "TICK-TEST-AMB",
        "message": "help please urgently system error broken"
    }
    res = client.post("/tickets", json=payload)
    assert res.status_code == 201
    data = res.json()
    
    assert data["needs_review"] is True
    assert data["review_reason"] is not None


def test_duplicate_ticket_id_rejection():
    """Scenario 3: Reject duplicate ticket IDs with 409 Conflict."""
    payload = {
        "ticket_id": "TICK-DUP-999",
        "message": "My password reset link email is not arriving in inbox."
    }
    # First creation should succeed
    res1 = client.post("/tickets", json=payload)
    assert res1.status_code == 201

    # Second creation with identical ID must fail with 409
    res2 = client.post("/tickets", json=payload)
    assert res2.status_code == 409
    assert "already exists" in res2.json()["detail"]


def test_invalid_input_validation():
    """Scenario 4: Reject invalid inputs (empty ticket_id or message too short)."""
    # Empty ticket_id
    res1 = client.post("/tickets", json={"ticket_id": "", "message": "Valid description message"})
    assert res1.status_code == 422

    # Message shorter than minimum constraint (5 characters)
    res2 = client.post("/tickets", json={"ticket_id": "TICK-INV-1", "message": "hi"})
    assert res2.status_code == 422


def test_human_approval_workflow_and_audit_trail():
    """Scenario 5: Draft response approval and audit log trail verification."""
    # Create ticket
    payload = {
        "ticket_id": "TICK-APPR-001",
        "message": "Our security admin has been locked out after 3 failed MFA attempts."
    }
    client.post("/tickets", json=payload)

    # Approve draft response
    approval_payload = {
        "decision": "approved",
        "reviewer_name": "Sarah Connor (IAM Lead)",
        "notes": "Verified credentials with customer via phone.",
        "edited_draft_response": "Hello, your MFA lockout has been cleared. Please use your recovery key."
    }
    appr_res = client.post("/tickets/TICK-APPR-001/approve", json=approval_payload)
    assert appr_res.status_code == 200
    appr_data = appr_res.json()

    assert appr_data["status"] == "approved"
    assert appr_data["approved_by"] == "Sarah Connor (IAM Lead)"
    assert "recovery key" in appr_data["draft_response"]

    # Verify audit log trail
    audit_res = client.get("/tickets/TICK-APPR-001/audit")
    assert audit_res.status_code == 200
    events = audit_res.json()["audit_events"]
    assert len(events) >= 2  # CREATED + STATUS_CHANGE_APPROVED
    assert events[0]["action"] == "CREATED"
    assert events[1]["action"] == "STATUS_CHANGE_APPROVED"


def test_test_set_accuracy_metric():
    """Scenario 6: Test set accuracy metric exceeds baseline requirements (>= 80%)."""
    res = client.get("/metrics/accuracy")
    assert res.status_code == 200
    data = res.json()
    assert data["total_test_samples"] == 10
    assert data["accuracy_percentage"] >= 80.0


def test_automatic_ticket_id_generation():
    """Verify that omitting ticket_id automatically generates a formatted TCK-XXXXXXXX ID."""
    payload = {
        "message": "Cannot log in using single sign-on SAML authentication."
    }
    res = client.post("/tickets", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert "ticket_id" in data
    assert data["ticket_id"].startswith("TCK-")
    assert len(data["ticket_id"]) == 12
    assert data["category"] == "Access"


def test_list_tickets_filtering():
    """Verify category and status filters on /tickets endpoint."""
    # Create billing ticket
    client.post("/tickets", json={"ticket_id": "TICK-FILT-1", "message": "Double billed on my Visa card invoice"})
    # Create technical ticket
    client.post("/tickets", json={"ticket_id": "TICK-FILT-2", "message": "Database query timeout throwing 500 error"})

    # Filter by category
    res = client.get("/tickets?category=Billing")
    assert res.status_code == 200
    items = res.json()
    assert all(i["category"] == "Billing" for i in items)

    # Filter with invalid category
    bad_res = client.get("/tickets?category=NonExistentCategory")
    assert bad_res.status_code == 400


def test_ticket_not_found():
    """Verify 404 response for non-existent ticket endpoints."""
    res_get = client.get("/tickets/NON-EXISTENT-ID")
    assert res_get.status_code == 404

    res_appr = client.post("/tickets/NON-EXISTENT-ID/approve", json={"decision": "approved", "reviewer_name": "Test"})
    assert res_appr.status_code == 404

    res_audit = client.get("/tickets/NON-EXISTENT-ID/audit")
    assert res_audit.status_code == 404


