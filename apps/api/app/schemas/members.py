"""Contracts of a member's rights (ADR-0015): the member list, the export, the erasure."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class MemberOut(BaseModel):
    user_id: str
    display_name: str
    email: str | None
    role: str
    role_label: str
    is_owner: bool  # owns a workspace: cannot be erased
    created_at: datetime


class ErasureOut(BaseModel):
    user_id: str
    anonymised: bool  # False: still a member of another workspace, identity kept


class ExportProfile(BaseModel):
    user_id: str
    display_name: str
    email: str | None
    sso_subject: str | None
    created_at: datetime


class ExportMembership(BaseModel):
    workspace_id: str
    workspace_name: str
    role: str


class ExportSession(BaseModel):
    """Dates only: the token hash would be of no use to the member, and is a credential."""

    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None


class ExportAuditEntry(BaseModel):
    timestamp: datetime
    workspace_id: str | None
    action: str
    target: str
    decision: str | None
    details: dict[str, Any]


class ExportApproval(BaseModel):
    run_id: str
    action_type: str
    summary: str
    status: str
    requested: bool  # the member asked for it
    decided: bool  # the member decided it
    created_at: datetime
    decided_at: datetime | None


class MemberExport(BaseModel):
    """Everything NFactory links to the member. Runs and projects belong to the workspace,
    not to a member, so they are not in it."""

    generated_at: datetime
    profile: ExportProfile
    memberships: list[ExportMembership]
    sessions: list[ExportSession]
    audit_entries: list[ExportAuditEntry]
    approvals: list[ExportApproval]
