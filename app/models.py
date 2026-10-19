"""
Data models and schemas for Support Ticket Automation.
"""

from typing import Optional, Literal
from pydantic import BaseModel, Field


CategoryType = Literal["Billing", "Technical", "Access", "General"]
PriorityType = Literal["Low", "Medium", "High", "Critical"]
StatusType = Literal["pending_review", "approved", "rejected"]


class TicketCreateRequest(BaseModel):
    ticket_id: Optional[str] = Field(None, min_length=3, max_length=64, description="Optional ticket ID; if omitted, one will be auto-generated")
    message: str = Field(..., min_length=5, description="Customer issue description / support query")


class TicketClassification(BaseModel):
    category: CategoryType
    confidence: float = Field(..., ge=0.0, le=1.0)
    priority: PriorityType
    priority_reason: str
    assigned_team: str
    summary: str
    draft_response: str
    needs_review: bool
    review_reason: Optional[str] = None


class TicketRecord(BaseModel):
    ticket_id: str
    message: str
    category: CategoryType
    confidence: float
    priority: PriorityType
    priority_reason: str
    assigned_team: str
    summary: str
    draft_response: str
    status: StatusType = "pending_review"
    needs_review: bool = False
    review_reason: Optional[str] = None
    created_at: str
    updated_at: str
    approved_by: Optional[str] = None
    approval_notes: Optional[str] = None


class ApprovalRequest(BaseModel):
    decision: Literal["approved", "rejected"]
    reviewer_name: str = Field(..., min_length=2)
    notes: Optional[str] = None
    edited_draft_response: Optional[str] = None


class AccuracyMetrics(BaseModel):
    total_test_samples: int
    correct_predictions: int
    accuracy_percentage: float
    category_breakdown: dict
