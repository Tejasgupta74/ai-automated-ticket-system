"""
FastAPI application for Cerevyn Azure Support Ticket Automation (PS04).
"""

from contextlib import asynccontextmanager
from typing import Optional, List
from fastapi import FastAPI, HTTPException, status, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from app.models import (
    TicketCreateRequest,
    TicketRecord,
    ApprovalRequest,
    AccuracyMetrics
)
from app.classifier import classifier_engine
from app.database import (
    init_db,
    get_ticket,
    insert_ticket,
    update_ticket_approval,
    list_all_tickets,
    get_audit_trail
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize database tables
    init_db()
    yield


app = FastAPI(
    title="Cerevyn Azure Support Ticket Automation API",
    description="PS04 Technical Assessment Solution: AI Ticket Classifier, Priority Policy, Review Triage, and Audit Logs.",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for browser interfaces or integration clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["System"])
def health_check():
    """Liveness probe endpoint for Azure App Service & container orchestrators."""
    return {
        "status": "healthy",
        "service": "cerevyn-support-ticket-automation",
        "classifier_ready": classifier_engine.is_trained
    }


@app.post(
    "/tickets",
    response_model=TicketRecord,
    status_code=status.HTTP_201_CREATED,
    tags=["Tickets"]
)
def create_ticket(req: TicketCreateRequest):
    """
    Ingest a new support ticket.
    - Rejects duplicate ticket IDs (409 Conflict).
    - Classifies category, assigns priority policy, selects assigned team, generates summary & draft response.
    - Flags uncertain or ambiguous tickets for manual review.
    - Saves ticket in pending_review status.
    """
    # 1. Validation & Duplicate check
    existing = get_ticket(req.ticket_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Duplicate ticket ID: Ticket '{req.ticket_id}' already exists in the system."
        )

    # 2. Classifier & NLP reasoning
    classification = classifier_engine.classify_and_reason(req.message)

    # 3. Create persistent record
    ticket_payload = {
        "ticket_id": req.ticket_id,
        "message": req.message,
        **classification
    }

    created = insert_ticket(ticket_payload)
    return created


@app.get(
    "/tickets/{ticket_id}",
    response_model=TicketRecord,
    tags=["Tickets"]
)
def fetch_ticket(ticket_id: str):
    """Retrieve details and current status of a specific ticket."""
    ticket = get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket '{ticket_id}' not found."
        )
    return ticket


@app.get(
    "/tickets",
    response_model=List[TicketRecord],
    tags=["Tickets"]
)
def list_tickets(
    category: Optional[str] = Query(None, description="Filter by category (Billing, Technical, Access, General)"),
    status: Optional[str] = Query(None, description="Filter by status (pending_review, approved, rejected)")
):
    """List tickets with optional category or status filters."""
    return list_all_tickets(category=category, status=status)


@app.post(
    "/tickets/{ticket_id}/approve",
    response_model=TicketRecord,
    tags=["Human Review & Approval"]
)
def approve_ticket(ticket_id: str, req: ApprovalRequest):
    """
    Approve or reject a drafted ticket response.
    Drafts require explicit human review before being marked as ready/dispatched.
    """
    ticket = get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket '{ticket_id}' not found."
        )

    updated = update_ticket_approval(
        ticket_id=ticket_id,
        decision=req.decision,
        reviewer_name=req.reviewer_name,
        notes=req.notes,
        edited_draft_response=req.edited_draft_response
    )
    return updated


@app.get(
    "/tickets/{ticket_id}/audit",
    tags=["Human Review & Approval"]
)
def view_audit_log(ticket_id: str):
    """Retrieve lifecycle audit logs for compliance and state history."""
    ticket = get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket '{ticket_id}' not found."
        )
    logs = get_audit_trail(ticket_id)
    return {"ticket_id": ticket_id, "audit_events": logs}


@app.get(
    "/metrics/accuracy",
    response_model=AccuracyMetrics,
    tags=["Metrics & Evaluation"]
)
def get_model_accuracy():
    """
    Evaluates classification accuracy on the reserved 10-ticket evaluation set.
    """
    return classifier_engine.evaluate_test_set()


@app.get("/", response_class=HTMLResponse, tags=["Dashboard"])
def get_dashboard():
    """Interactive single-page web dashboard for live evaluation & demonstration."""
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Cerevyn Support Ticket Automation - PS04</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body { background: #0f172a; color: #f8fafc; font-family: system-ui, -apple-system, sans-serif; }
            .card { background: #1e293b; border: 1px solid #334155; color: #f8fafc; border-radius: 10px; }
            .badge-Critical { background: #ef4444; }
            .badge-High { background: #f97316; }
            .badge-Medium { background: #eab308; color: #1e293b; }
            .badge-Low { background: #22c55e; }
            pre { background: #0f172a; color: #38bdf8; padding: 12px; border-radius: 6px; font-size: 0.85rem; }
            .table-dark { --bs-table-bg: #1e293b; }
        </style>
    </head>
    <body class="p-4">
        <div class="container-fluid">
            <header class="d-flex justify-content-between align-items-center mb-4 pb-3 border-bottom border-secondary">
                <div>
                    <h2 class="fw-bold mb-0 text-info">Cerevyn AI Support Ticket Automation (PS04)</h2>
                    <p class="text-secondary mb-0">FastAPI &bull; Scikit-Learn NLP &bull; Priority Engine &bull; Review Gateway</p>
                </div>
                <div>
                    <a href="/docs" target="_blank" class="btn btn-outline-info me-2">Interactive Swagger API</a>
                    <button class="btn btn-primary" onclick="loadAccuracy()">Check Model Accuracy</button>
                </div>
            </header>

            <div class="row g-4">
                <!-- Submission Form -->
                <div class="col-lg-5">
                    <div class="card p-4 shadow-sm mb-4">
                        <h5 class="fw-bold text-white mb-3">Submit New Support Ticket</h5>
                        <form id="ticketForm" onsubmit="submitTicket(event)">
                            <div class="mb-3">
                                <label class="form-label text-secondary">Ticket ID</label>
                                <input type="text" id="ticketId" class="form-control bg-dark text-white border-secondary" required placeholder="e.g. TC-DEMO-101">
                            </div>
                            <div class="mb-3">
                                <label class="form-label text-secondary">Message / Issue Details</label>
                                <textarea id="ticketMsg" class="form-control bg-dark text-white border-secondary" rows="3" required placeholder="e.g. Payment failed via card and team account suspended..."></textarea>
                            </div>
                            <div class="d-flex gap-2">
                                <button type="submit" class="btn btn-success flex-grow-1">Classify &amp; Ingest Ticket</button>
                                <button type="button" class="btn btn-outline-warning" onclick="fillSample('critical')">Critical Demo</button>
                                <button type="button" class="btn btn-outline-secondary" onclick="fillSample('ambiguous')">Ambiguous Demo</button>
                            </div>
                        </form>
                    </div>

                    <div class="card p-4 shadow-sm" id="metricsCard">
                        <h5 class="fw-bold text-white mb-2">Reserved Test Set Evaluation</h5>
                        <p class="text-secondary small mb-3">Evaluated automatically against 10 unseen reserved test tickets.</p>
                        <div id="metricsOutput" class="small text-muted">Click "Check Model Accuracy" above to evaluate.</div>
                    </div>
                </div>

                <!-- Tickets List & Inspection -->
                <div class="col-lg-7">
                    <div class="card p-4 shadow-sm">
                        <div class="d-flex justify-content-between align-items-center mb-3">
                            <h5 class="fw-bold text-white mb-0">Active Tickets &amp; Human Approval Workflow</h5>
                            <button class="btn btn-sm btn-outline-light" onclick="fetchTickets()">Refresh List</button>
                        </div>
                        <div class="table-responsive">
                            <table class="table table-dark table-hover align-middle mb-0">
                                <thead>
                                    <tr>
                                        <th>ID</th>
                                        <th>Category</th>
                                        <th>Priority</th>
                                        <th>Status</th>
                                        <th>Review Flag</th>
                                        <th>Action</th>
                                    </tr>
                                </thead>
                                <tbody id="ticketListBody">
                                    <tr><td colspan="6" class="text-center text-muted">No tickets loaded. Submit one or refresh.</td></tr>
                                </tbody>
                            </table>
                        </div>
                    </div>

                    <!-- Details Modal / Box -->
                    <div class="card p-4 shadow-sm mt-4" id="detailsSection" style="display:none;">
                        <h5 class="fw-bold text-info" id="detailTitle">Ticket Details</h5>
                        <div id="detailContent"></div>
                    </div>
                </div>
            </div>
        </div>

        <script>
            async function fetchTickets() {
                const res = await fetch('/tickets');
                const tickets = await res.json();
                const tbody = document.getElementById('ticketListBody');
                tbody.innerHTML = '';
                if (tickets.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted">No tickets found.</td></tr>';
                    return;
                }
                tickets.forEach(t => {
                    const tr = document.createElement('tr');
                    tr.innerHTML = `
                        <td class="fw-bold text-light">${t.ticket_id}</td>
                        <td><span class="badge bg-secondary">${t.category}</span> (${Math.round(t.confidence*100)}%)</td>
                        <td><span class="badge badge-${t.priority}">${t.priority}</span></td>
                        <td><span class="badge ${t.status === 'approved' ? 'bg-success' : (t.status === 'rejected' ? 'bg-danger' : 'bg-warning text-dark')}">${t.status}</span></td>
                        <td>${t.needs_review ? '<span class="badge bg-danger">Needs Review</span>' : '<span class="badge bg-success">Auto-Approved</span>'}</td>
                        <td>
                            <button class="btn btn-xs btn-outline-info py-0 px-2" onclick="showTicket('${t.ticket_id}')">View</button>
                        </td>
                    `;
                    tbody.appendChild(tr);
                });
            }

            async function submitTicket(e) {
                e.preventDefault();
                const ticket_id = document.getElementById('ticketId').value.trim();
                const message = document.getElementById('ticketMsg').value.trim();
                try {
                    const res = await fetch('/tickets', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({ ticket_id, message })
                    });
                    if (!res.ok) {
                        const err = await res.json();
                        alert('Error: ' + (err.detail || res.statusText));
                        return;
                    }
                    const data = await res.json();
                    document.getElementById('ticketId').value = '';
                    document.getElementById('ticketMsg').value = '';
                    await fetchTickets();
                    showTicket(data.ticket_id);
                } catch(err) {
                    alert('Submission error: ' + err);
                }
            }

            async function showTicket(id) {
                const res = await fetch('/tickets/' + id);
                const t = await res.json();
                const auditRes = await fetch('/tickets/' + id + '/audit');
                const audit = await auditRes.json();
                
                document.getElementById('detailsSection').style.display = 'block';
                document.getElementById('detailTitle').innerText = 'Ticket: ' + t.ticket_id + ' (' + t.category + ')';
                document.getElementById('detailContent').innerHTML = `
                    <div class="row mb-3">
                        <div class="col-md-6">
                            <strong>Assigned Team:</strong> ${t.assigned_team}<br>
                            <strong>Priority:</strong> <span class="badge badge-${t.priority}">${t.priority}</span> (${t.priority_reason})<br>
                            <strong>Confidence:</strong> ${Math.round(t.confidence*100)}%
                        </div>
                        <div class="col-md-6">
                            <strong>Status:</strong> ${t.status}<br>
                            <strong>Needs Review:</strong> ${t.needs_review ? '⚠️ ' + (t.review_reason || 'Yes') : 'No'}<br>
                            <strong>Approved By:</strong> ${t.approved_by || 'Pending human sign-off'}
                        </div>
                    </div>
                    <h6>Summary:</h6>
                    <p class="text-light fst-italic">${t.summary}</p>
                    <h6>Draft Response:</h6>
                    <pre>${t.draft_response}</pre>
                    ${t.status === 'pending_review' ? `
                        <div class="d-flex gap-2 mt-3">
                            <button class="btn btn-sm btn-success" onclick="approveTicket('${t.ticket_id}', 'approved')">Approve Draft Response</button>
                            <button class="btn btn-sm btn-danger" onclick="approveTicket('${t.ticket_id}', 'rejected')">Reject / Request Edit</button>
                        </div>
                    ` : ''}
                    <h6 class="mt-4">Audit Trail:</h6>
                    <div class="small text-secondary">
                        ${audit.audit_events.map(ev => `<div>[${ev.timestamp}] <strong>${ev.action}</strong> by <em>${ev.performed_by}</em>: ${ev.notes}</div>`).join('')}
                    </div>
                `;
            }

            async function approveTicket(id, decision) {
                const reviewer = prompt('Enter your reviewer name:', 'Senior Support Lead');
                if (!reviewer) return;
                const notes = prompt('Enter review notes:', 'Draft response reviewed and validated.');
                await fetch('/tickets/' + id + '/approve', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ decision, reviewer_name: reviewer, notes })
                });
                fetchTickets();
                showTicket(id);
            }

            async function loadAccuracy() {
                const res = await fetch('/metrics/accuracy');
                const data = await res.json();
                document.getElementById('metricsOutput').innerHTML = `
                    <div class="alert alert-info py-2">
                        <strong>Test Set Accuracy:</strong> ${data.accuracy_percentage}% (${data.correct_predictions}/${data.total_test_samples} correct)
                    </div>
                    <pre>${JSON.stringify(data.category_breakdown, null, 2)}</pre>
                `;
            }

            function fillSample(type) {
                if (type === 'critical') {
                    document.getElementById('ticketId').value = 'TICK-PROD-' + Math.floor(Math.random()*900 + 100);
                    document.getElementById('ticketMsg').value = 'Production database timeout throwing 500 internal server error for all users!';
                } else {
                    document.getElementById('ticketId').value = 'TICK-AMB-' + Math.floor(Math.random()*900 + 100);
                    document.getElementById('ticketMsg').value = 'help please urgently system error broken';
                }
            }

            // Load on start
            fetchTickets();
            loadAccuracy();
        </script>
    </body>
    </html>
    """
