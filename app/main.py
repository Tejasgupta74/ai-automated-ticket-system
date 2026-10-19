"""
FastAPI application for Cerevyn Azure Support Ticket Automation (PS04).
"""

from contextlib import asynccontextmanager
from typing import Optional, List
import uuid
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
    # 1. Ticket ID resolution & Duplicate check
    ticket_id = (req.ticket_id or "").strip()
    if not ticket_id:
        # Generate formatted auto-ID, e.g., TCK-A1B2C3D4
        ticket_id = f"TCK-{uuid.uuid4().hex[:8].upper()}"
    else:
        existing = get_ticket(ticket_id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Duplicate ticket ID: Ticket '{ticket_id}' already exists in the system."
            )

    # 2. Classifier & NLP reasoning
    classification = classifier_engine.classify_and_reason(req.message)

    # 3. Create persistent record
    ticket_payload = {
        "ticket_id": ticket_id,
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
    valid_categories = {"Billing", "Technical", "Access", "General"}
    valid_statuses = {"pending_review", "approved", "rejected"}
    if category and category not in valid_categories:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category filter '{category}'. Must be one of: {sorted(list(valid_categories))}"
        )
    if status and status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status filter '{status}'. Must be one of: {sorted(list(valid_statuses))}"
        )
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
            body { background: #0b1120; color: #f8fafc; font-family: system-ui, -apple-system, sans-serif; }
            .card { background: #1e293b; border: 1px solid #334155; color: #f8fafc; border-radius: 12px; }
            .badge-Critical { background: #ef4444; }
            .badge-High { background: #f97316; }
            .badge-Medium { background: #eab308; color: #0f172a; font-weight: 600; }
            .badge-Low { background: #22c55e; }
            pre { background: #0f172a; color: #38bdf8; padding: 14px; border-radius: 8px; font-size: 0.88rem; border: 1px solid #1e293b; white-space: pre-wrap; word-break: break-word; }
            .table-dark { --bs-table-bg: #1e293b; }
            .metric-box { background: #0f172a; border-radius: 8px; padding: 12px; border: 1px solid #334155; }
        </style>
    </head>
    <body class="p-4">
        <div class="container-fluid" style="max-width: 1440px;">
            <header class="d-flex flex-wrap justify-content-between align-items-center mb-4 pb-3 border-bottom border-secondary gap-3">
                <div>
                    <div class="d-flex align-items-center gap-2">
                        <span class="badge bg-primary px-3 py-2 fs-6">PS04 Production</span>
                        <h2 class="fw-bold mb-0 text-info">Cerevyn AI Support Ticket Automation</h2>
                    </div>
                    <p class="text-secondary mb-0 small mt-1">FastAPI &bull; Scikit-Learn NLP &bull; SLA Priority Engine &bull; Review Gateway &bull; SQLite/MySQL Ready</p>
                </div>
                <div class="d-flex gap-2">
                    <a href="/docs" target="_blank" class="btn btn-outline-info">Swagger API</a>
                    <button class="btn btn-primary" onclick="loadAccuracy()">Check Model Accuracy</button>
                </div>
            </header>

            <div class="row g-4">
                <!-- Left Column: Ingestion & Live Metrics -->
                <div class="col-lg-5">
                    <div class="card p-4 shadow-sm mb-4">
                        <h5 class="fw-bold text-white mb-3">Submit Support Ticket</h5>
                        <form id="ticketForm" onsubmit="submitTicket(event)">
                            <div class="mb-3">
                                <label class="form-label text-secondary small text-uppercase fw-semibold">Ticket ID <span class="text-muted">(Optional - leave blank to auto-generate)</span></label>
                                <input type="text" id="ticketId" class="form-control bg-dark text-white border-secondary" placeholder="e.g. TC-DEMO-101 (or leave blank)">
                            </div>
                            <div class="mb-3">
                                <label class="form-label text-secondary small text-uppercase fw-semibold">Message / Issue Details</label>
                                <textarea id="ticketMsg" class="form-control bg-dark text-white border-secondary" rows="3" required placeholder="Describe issue (e.g. Production database timeout 500 error, unauthorized charge, login lockout)..."></textarea>
                            </div>
                            <div class="d-flex flex-wrap gap-2">
                                <button type="submit" class="btn btn-success flex-grow-1" id="submitBtn">Classify &amp; Ingest Ticket</button>
                                <button type="button" class="btn btn-outline-warning btn-sm" onclick="fillSample('critical')">Critical Outage</button>
                                <button type="button" class="btn btn-outline-info btn-sm" onclick="fillSample('billing')">Double Charge</button>
                                <button type="button" class="btn btn-outline-secondary btn-sm" onclick="fillSample('ambiguous')">Ambiguous Inquiry</button>
                            </div>
                        </form>
                    </div>

                    <div class="card p-4 shadow-sm" id="metricsCard">
                        <div class="d-flex justify-content-between align-items-center mb-2">
                            <h5 class="fw-bold text-white mb-0">Reserved Test Set Evaluation</h5>
                            <span class="badge bg-info text-dark" id="accuracyBadge">Ready</span>
                        </div>
                        <p class="text-secondary small mb-3">Automatically assessed against the 10 unseen reserved test tickets specified by the assessment.</p>
                        <div id="metricsOutput" class="small text-muted">Click "Check Model Accuracy" above to run live evaluation.</div>
                    </div>
                </div>

                <!-- Right Column: Tickets List & Inspection -->
                <div class="col-lg-7">
                    <div class="card p-4 shadow-sm mb-4">
                        <div class="d-flex flex-wrap justify-content-between align-items-center mb-3 gap-2">
                            <h5 class="fw-bold text-white mb-0">Active Tickets Queue</h5>
                            <div class="d-flex align-items-center gap-2">
                                <select id="filterCategory" class="form-select form-select-sm bg-dark text-white border-secondary" style="width: auto;" onchange="fetchTickets()">
                                    <option value="">All Categories</option>
                                    <option value="Billing">Billing</option>
                                    <option value="Technical">Technical</option>
                                    <option value="Access">Access</option>
                                    <option value="General">General</option>
                                </select>
                                <select id="filterStatus" class="form-select form-select-sm bg-dark text-white border-secondary" style="width: auto;" onchange="fetchTickets()">
                                    <option value="">All Statuses</option>
                                    <option value="pending_review">Pending Review</option>
                                    <option value="approved">Approved</option>
                                    <option value="rejected">Rejected</option>
                                </select>
                                <button class="btn btn-sm btn-outline-light" onclick="fetchTickets()">Refresh</button>
                            </div>
                        </div>
                        <div class="table-responsive">
                            <table class="table table-dark table-hover align-middle mb-0">
                                <thead>
                                    <tr class="text-secondary small text-uppercase">
                                        <th>Ticket ID</th>
                                        <th>Category</th>
                                        <th>Priority</th>
                                        <th>Status</th>
                                        <th>Triage</th>
                                        <th class="text-end">Action</th>
                                    </tr>
                                </thead>
                                <tbody id="ticketListBody">
                                    <tr><td colspan="6" class="text-center text-muted py-3">Loading tickets...</td></tr>
                                </tbody>
                            </table>
                        </div>
                    </div>

                    <!-- Details Box -->
                    <div class="card p-4 shadow-sm" id="detailsSection" style="display:none;">
                        <div class="d-flex justify-content-between align-items-center mb-3">
                            <h5 class="fw-bold text-info mb-0" id="detailTitle">Ticket Details</h5>
                            <button class="btn btn-sm btn-outline-secondary" onclick="document.getElementById('detailsSection').style.display='none'">Close</button>
                        </div>
                        <div id="detailContent"></div>
                    </div>
                </div>
            </div>
        </div>

        <script>
            function escapeHtml(str) {
                if (!str) return '';
                const div = document.createElement('div');
                div.textContent = str;
                return div.innerHTML;
            }

            async function fetchTickets() {
                const cat = document.getElementById('filterCategory').value;
                const stat = document.getElementById('filterStatus').value;
                const params = new URLSearchParams();
                if (cat) params.append('category', cat);
                if (stat) params.append('status', stat);

                try {
                    const res = await fetch('/tickets?' + params.toString());
                    const tickets = await res.json();
                    const tbody = document.getElementById('ticketListBody');
                    tbody.innerHTML = '';
                    if (!tickets || tickets.length === 0) {
                        tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted py-3">No tickets found for current filters.</td></tr>';
                        return;
                    }
                    tickets.forEach(t => {
                        const tr = document.createElement('tr');
                        const statusClass = t.status === 'approved' ? 'bg-success' : (t.status === 'rejected' ? 'bg-danger' : 'bg-warning text-dark');
                        const triageBadge = t.needs_review ? '<span class="badge bg-danger">Needs Review</span>' : '<span class="badge bg-success">Auto-Approved</span>';
                        tr.innerHTML = `
                            <td class="fw-bold text-light">${escapeHtml(t.ticket_id)}</td>
                            <td><span class="badge bg-secondary">${escapeHtml(t.category)}</span> <span class="text-muted small">(${Math.round(t.confidence*100)}%)</span></td>
                            <td><span class="badge badge-${escapeHtml(t.priority)}">${escapeHtml(t.priority)}</span></td>
                            <td><span class="badge ${statusClass}">${escapeHtml(t.status)}</span></td>
                            <td>${triageBadge}</td>
                            <td class="text-end">
                                <button class="btn btn-xs btn-outline-info py-0 px-2" onclick="showTicket('${escapeHtml(t.ticket_id)}')">Inspect</button>
                            </td>
                        `;
                        tbody.appendChild(tr);
                    });
                } catch(err) {
                    console.error('Fetch error:', err);
                }
            }

            async function submitTicket(e) {
                e.preventDefault();
                const rawId = document.getElementById('ticketId').value.trim();
                const ticket_id = rawId ? rawId : null;
                const message = document.getElementById('ticketMsg').value.trim();
                const submitBtn = document.getElementById('submitBtn');
                submitBtn.disabled = true;

                try {
                    const payload = { message };
                    if (ticket_id) payload.ticket_id = ticket_id;
                    const res = await fetch('/tickets', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify(payload)
                    });
                    if (!res.ok) {
                        const err = await res.json();
                        alert('Error: ' + (err.detail || res.statusText));
                        submitBtn.disabled = false;
                        return;
                    }
                    const data = await res.json();
                    document.getElementById('ticketId').value = '';
                    document.getElementById('ticketMsg').value = '';
                    await fetchTickets();
                    showTicket(data.ticket_id);
                } catch(err) {
                    alert('Submission error: ' + err);
                } finally {
                    submitBtn.disabled = false;
                }
            }

            async function showTicket(id) {
                try {
                    const res = await fetch('/tickets/' + encodeURIComponent(id));
                    if (!res.ok) { alert('Could not find ticket'); return; }
                    const t = await res.json();
                    const auditRes = await fetch('/tickets/' + encodeURIComponent(id) + '/audit');
                    const audit = await auditRes.json();
                    
                    document.getElementById('detailsSection').style.display = 'block';
                    document.getElementById('detailTitle').innerText = 'Ticket: ' + t.ticket_id + ' (' + t.category + ')';
                    
                    const auditHtml = (audit.audit_events || []).map(ev => 
                        `<div class="py-1 border-bottom border-dark">
                            <span class="text-muted small">[${escapeHtml(ev.timestamp)}]</span>
                            <span class="badge bg-secondary ms-1">${escapeHtml(ev.action)}</span>
                            <span class="text-info ms-1">by ${escapeHtml(ev.performed_by)}</span>: 
                            <span class="text-light">${escapeHtml(ev.notes || '')}</span>
                        </div>`
                    ).join('');

                    document.getElementById('detailContent').innerHTML = `
                        <div class="row g-3 mb-3">
                            <div class="col-md-6">
                                <div class="metric-box">
                                    <div class="text-muted small">Assigned Team</div>
                                    <div class="fw-bold text-info">${escapeHtml(t.assigned_team)}</div>
                                    <div class="text-muted small mt-2">Priority &amp; SLA Rule</div>
                                    <div><span class="badge badge-${escapeHtml(t.priority)}">${escapeHtml(t.priority)}</span> <span class="small text-secondary">(${escapeHtml(t.priority_reason)})</span></div>
                                    <div class="text-muted small mt-2">Model Confidence</div>
                                    <div class="fw-semibold">${Math.round(t.confidence*100)}%</div>
                                </div>
                            </div>
                            <div class="col-md-6">
                                <div class="metric-box">
                                    <div class="text-muted small">Current Lifecycle Status</div>
                                    <div class="fw-bold">${escapeHtml(t.status)}</div>
                                    <div class="text-muted small mt-2">Human Triage Flag</div>
                                    <div>${t.needs_review ? '<span class="badge bg-danger">Needs Review</span> <span class="small text-warning">(' + escapeHtml(t.review_reason || '') + ')</span>' : '<span class="badge bg-success">Automated Confidence High</span>'}</div>
                                    <div class="text-muted small mt-2">Approved By</div>
                                    <div class="text-light">${escapeHtml(t.approved_by || 'Pending human sign-off')}</div>
                                </div>
                            </div>
                        </div>

                        <div class="mb-3">
                            <label class="text-secondary small text-uppercase fw-semibold">Customer Message</label>
                            <p class="text-light bg-dark p-2 rounded">${escapeHtml(t.message)}</p>
                        </div>

                        <div class="mb-3">
                            <label class="text-secondary small text-uppercase fw-semibold">AI Generated Summary</label>
                            <p class="text-light fst-italic mb-2">${escapeHtml(t.summary)}</p>
                        </div>

                        <div class="mb-3">
                            <label class="text-secondary small text-uppercase fw-semibold">Prepared Draft Response</label>
                            <pre>${escapeHtml(t.draft_response)}</pre>
                        </div>

                        ${t.status === 'pending_review' ? `
                            <div class="d-flex gap-2 my-3 p-3 bg-dark rounded border border-secondary">
                                <button class="btn btn-success flex-grow-1" onclick="approveTicket('${escapeHtml(t.ticket_id)}', 'approved')">Approve Draft Response</button>
                                <button class="btn btn-danger flex-grow-1" onclick="approveTicket('${escapeHtml(t.ticket_id)}', 'rejected')">Reject / Request Edit</button>
                            </div>
                        ` : ''}

                        <h6 class="mt-4 text-info fw-bold">Immutable Audit Trail</h6>
                        <div class="bg-dark p-3 rounded small">
                            ${auditHtml || '<span class="text-muted">No audit events recorded.</span>'}
                        </div>
                    `;
                } catch(err) {
                    console.error('Inspection error:', err);
                }
            }

            async function approveTicket(id, decision) {
                const reviewer = prompt('Enter reviewer name or role:', 'Senior Support Lead');
                if (!reviewer) return;
                const notes = prompt('Enter review notes / reason:', decision === 'approved' ? 'Draft response reviewed and validated.' : 'Draft requires revision.');
                try {
                    const res = await fetch('/tickets/' + encodeURIComponent(id) + '/approve', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({ decision, reviewer_name: reviewer, notes })
                    });
                    if (!res.ok) {
                        const err = await res.json();
                        alert('Approval failed: ' + (err.detail || res.statusText));
                        return;
                    }
                    await fetchTickets();
                    await showTicket(id);
                } catch(err) {
                    alert('Approval error: ' + err);
                }
            }

            async function loadAccuracy() {
                try {
                    const res = await fetch('/metrics/accuracy');
                    const data = await res.json();
                    document.getElementById('accuracyBadge').innerText = data.accuracy_percentage + '% Accuracy';
                    document.getElementById('metricsOutput').innerHTML = `
                        <div class="alert alert-info py-2 mb-2">
                            <strong>Observed Test Accuracy:</strong> ${data.accuracy_percentage}% (${data.correct_predictions} of ${data.total_test_samples} correct)
                        </div>
                        <pre class="mb-0">${escapeHtml(JSON.stringify(data.category_breakdown, null, 2))}</pre>
                    `;
                } catch(err) {
                    console.error('Accuracy error:', err);
                }
            }

            function fillSample(type) {
                if (type === 'critical') {
                    document.getElementById('ticketId').value = '';
                    document.getElementById('ticketMsg').value = 'Production database timeout throwing 500 internal server error for all web clients!';
                } else if (type === 'billing') {
                    document.getElementById('ticketId').value = '';
                    document.getElementById('ticketMsg').value = 'I was double charged on my credit card for the monthly subscription invoice #99283.';
                } else {
                    document.getElementById('ticketId').value = '';
                    document.getElementById('ticketMsg').value = 'help please urgently system error broken';
                }
            }

            // Initial load
            fetchTickets();
            loadAccuracy();
        </script>
    </body>
    </html>
    """
