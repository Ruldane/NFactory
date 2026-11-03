"""Contracts of RBAC, the audit log and the approval center (task 5.4)."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class WorkspaceAccess(BaseModel):
    id: str
    name: str
    role: str
    role_label: str
    permissions: list[str]


class MeOut(BaseModel):
    user_id: str
    display_name: str
    workspaces: list[WorkspaceAccess]


class AuditEntry(BaseModel):
    id: int
    timestamp: datetime
    actor_id: str | None
    actor_name: str | None
    action: str
    target: str
    decision: str | None
    details: dict[str, Any]


class AuditPage(BaseModel):
    items: list[AuditEntry]
    next_before: int | None  # pass as `before` for the next, older page


class ApprovalItem(BaseModel):
    id: str
    status: str
    action_type: str
    action_label: str
    summary: str
    run_id: str
    run_state: str
    project_id: str
    project_title: str
    created_at: datetime
    decided_at: datetime | None
