"""
SQLite-backed database layer for Ticket persistence, state management, and audit log.
"""

import sqlite3
import os
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

DB_PATH = os.environ.get("SQLITE_DB_PATH", os.path.join(os.path.dirname(__file__), "..", "tickets.db"))

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode = WAL;")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                ticket_id TEXT PRIMARY KEY,
                message TEXT NOT NULL,
                category TEXT NOT NULL,
                confidence REAL NOT NULL,
                priority TEXT NOT NULL,
                priority_reason TEXT NOT NULL,
                assigned_team TEXT NOT NULL,
                summary TEXT NOT NULL,
                draft_response TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending_review',
                needs_review INTEGER NOT NULL DEFAULT 0,
                review_reason TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                approved_by TEXT,
                approval_notes TEXT
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id TEXT NOT NULL,
                action TEXT NOT NULL,
                performed_by TEXT NOT NULL,
                notes TEXT,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (ticket_id) REFERENCES tickets(ticket_id) ON DELETE CASCADE
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tickets_category ON tickets(category);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tickets_created_at ON tickets(created_at);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_ticket_id ON audit_logs(ticket_id);")
        conn.commit()

def get_ticket(ticket_id: str) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tickets WHERE ticket_id = ?", (ticket_id,))
        row = cursor.fetchone()
        if not row:
            return None
        d = dict(row)
        d["needs_review"] = bool(d["needs_review"])
        return d

def insert_ticket(ticket_data: Dict[str, Any]) -> Dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    ticket_data["created_at"] = now
    ticket_data["updated_at"] = now
    ticket_data["status"] = "pending_review"

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO tickets (
                ticket_id, message, category, confidence, priority, priority_reason,
                assigned_team, summary, draft_response, status, needs_review,
                review_reason, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            ticket_data["ticket_id"],
            ticket_data["message"],
            ticket_data["category"],
            ticket_data["confidence"],
            ticket_data["priority"],
            ticket_data["priority_reason"],
            ticket_data["assigned_team"],
            ticket_data["summary"],
            ticket_data["draft_response"],
            ticket_data["status"],
            1 if ticket_data["needs_review"] else 0,
            ticket_data.get("review_reason"),
            ticket_data["created_at"],
            ticket_data["updated_at"]
        ))
        
        cursor.execute("""
            INSERT INTO audit_logs (ticket_id, action, performed_by, notes, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (
            ticket_data["ticket_id"],
            "CREATED",
            "SYSTEM_AI_CLASSIFIER",
            f"Assigned category {ticket_data['category']} with priority {ticket_data['priority']}",
            now
        ))
        conn.commit()

    return get_ticket(ticket_data["ticket_id"])

def update_ticket_approval(
    ticket_id: str,
    decision: str,
    reviewer_name: str,
    notes: Optional[str] = None,
    edited_draft_response: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    ticket = get_ticket(ticket_id)
    if not ticket:
        return None

    now = datetime.now(timezone.utc).isoformat()
    new_draft = edited_draft_response if edited_draft_response is not None else ticket["draft_response"]

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE tickets
            SET status = ?,
                draft_response = ?,
                approved_by = ?,
                approval_notes = ?,
                updated_at = ?
            WHERE ticket_id = ?
        """, (
            decision,
            new_draft,
            reviewer_name,
            notes,
            now,
            ticket_id
        ))

        cursor.execute("""
            INSERT INTO audit_logs (ticket_id, action, performed_by, notes, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (
            ticket_id,
            f"STATUS_CHANGE_{decision.upper()}",
            reviewer_name,
            notes or f"Marked as {decision}",
            now
        ))
        conn.commit()

    return get_ticket(ticket_id)

def list_all_tickets(category: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
    query = "SELECT * FROM tickets WHERE 1=1"
    params = []
    if category:
        query += " AND category = ?"
        params.append(category)
    if status:
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY created_at DESC"

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["needs_review"] = bool(d["needs_review"])
            results.append(d)
        return results

def get_audit_trail(ticket_id: str) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM audit_logs WHERE ticket_id = ? ORDER BY timestamp ASC", (ticket_id,))
        rows = cursor.fetchall()
        return [dict(r) for r in rows]
