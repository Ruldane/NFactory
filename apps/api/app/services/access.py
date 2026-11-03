"""Basic RBAC (task 5.4, spec F33): what each workspace role may do.

A route states the permission it needs; `permitted` narrows the request context to the
workspaces where the user's role grants it. Services already scope every query by
`ctx.workspace_ids`, so an ID elsewhere stays a 404, like a missing one. A user whose
default workspace does not grant the permission gets 403 `forbidden`.

Interface: PERMISSIONS, ROLE_LABELS, permissions_of, permitted.
"""

from dataclasses import replace
from typing import Literal

from app.errors import AppError
from app.services.identity import RequestContext

Permission = Literal["read", "approve", "audit", "build", "configure"]

# Explicit per role, not a ladder: a reviewer reads the audit log, a developer does not.
PERMISSIONS: dict[str, frozenset[Permission]] = {
    "owner": frozenset({"read", "approve", "audit", "build", "configure"}),
    "admin": frozenset({"read", "approve", "audit", "build", "configure"}),
    "developer": frozenset({"read", "approve", "build"}),
    "reviewer": frozenset({"read", "approve", "audit"}),
    "viewer": frozenset({"read"}),
}
ROLE_LABELS = {
    "owner": "Propriétaire",
    "admin": "Administrateur",
    "developer": "Développeur",
    "reviewer": "Relecteur",
    "viewer": "Lecteur",
}
_ACTIONS: dict[Permission, str] = {
    "read": "consulter",
    "approve": "décider d'une approbation",
    "audit": "lire le journal d'audit",
    "build": "créer, lancer ou modifier",
    "configure": "modifier la configuration",
}


def permissions_of(role: str | None) -> frozenset[Permission]:
    return PERMISSIONS.get(role or "", frozenset())


def permitted(ctx: RequestContext, permission: Permission) -> RequestContext:
    """The context limited to the workspaces where `permission` is granted."""
    allowed = frozenset(
        w for w in ctx.workspace_ids if permission in permissions_of(ctx.roles.get(w))
    )
    if ctx.default_workspace_id not in allowed:
        role = ctx.roles.get(ctx.default_workspace_id)
        who = (
            f"Votre rôle « {ROLE_LABELS.get(role, role)} »"
            if role
            else "Sans adhésion à cet espace de travail, vous"
        )
        verb = "ne permet pas de" if role else "ne pouvez pas"
        raise AppError(
            403,
            "forbidden",
            f"{who} {verb} {_ACTIONS[permission]}.",
            {"permission": permission, "role": role},
        )
    return replace(ctx, workspace_ids=allowed)
