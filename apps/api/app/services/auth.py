"""SSO sign-in use cases (ADR-0013): start a login, finish it, resolve and end sessions.

Admission is denied unless the account is listed: by its Google Workspace domain ("hd",
never the e-mail's domain) or by its verified e-mail. A member is found by issuer + sub.
The session cookie holds a random token; the table keeps only its SHA-256.
"""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import audit
from app.services.identity import LOCAL_WORKSPACE_ID, RequestContext
from app.services.oidc import Identity, OidcClient, OidcError
from nfactory_core.config import Settings
from nfactory_core.models import AuthSession, LoginAttempt, Membership, User

COOKIE = "nfactory_session"
LOGIN_TTL = timedelta(minutes=10)


class LoginRefused(Exception):
    """`code` is what the dashboard shows: state, not_allowed or provider."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _csv(value: str) -> frozenset[str]:
    return frozenset(v.strip().lower() for v in value.split(",") if v.strip())


@dataclass(frozen=True)
class Policy:
    domains: frozenset[str]
    emails: frozenset[str]
    owners: frozenset[str]
    ttl: timedelta

    @classmethod
    def from_settings(cls, settings: Settings) -> "Policy":
        return cls(
            domains=_csv(settings.nfactory_oidc_allowed_domains),
            emails=_csv(settings.nfactory_oidc_allowed_emails),
            owners=_csv(settings.nfactory_oidc_owner_emails),
            ttl=timedelta(hours=settings.nfactory_session_ttl_hours),
        )

    def role_for(self, identity: Identity) -> str | None:
        """The role a new member gets, or None when the account is not admitted."""
        listed = identity.email in self.emails or identity.email in self.owners
        in_domain = identity.hosted_domain is not None and identity.hosted_domain in self.domains
        if not (listed or in_domain):
            return None
        return "owner" if identity.email in self.owners else "viewer"


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def start_login(session: AsyncSession, oidc: OidcClient) -> str:
    now = datetime.now(UTC)
    await session.execute(delete(LoginAttempt).where(LoginAttempt.expires_at < now))
    attempt = LoginAttempt(
        state=secrets.token_urlsafe(32),
        nonce=secrets.token_urlsafe(24),
        verifier=secrets.token_urlsafe(64),
        expires_at=now + LOGIN_TTL,
    )
    session.add(attempt)
    url = await oidc.authorization_url(
        state=attempt.state, nonce=attempt.nonce, verifier=attempt.verifier
    )
    await session.commit()
    return url


async def finish_login(
    session: AsyncSession, oidc: OidcClient, policy: Policy, *, state: str, code: str
) -> str:
    """Returns the new session's token, or raises LoginRefused."""
    attempt = await session.get(LoginAttempt, state)
    if attempt is not None:
        await session.delete(attempt)  # used once, whatever happens next
        await session.commit()
    if attempt is None or attempt.expires_at < datetime.now(UTC):
        raise LoginRefused("state")
    try:
        identity = await oidc.exchange(code=code, verifier=attempt.verifier, nonce=attempt.nonce)
    except OidcError as exc:
        audit.record_anonymous(
            session,
            "auth.denied",
            "oidc",
            workspace_id=LOCAL_WORKSPACE_ID,
            decision="denied",
            details={"reason": exc.reason},
        )
        await session.commit()
        raise LoginRefused("provider") from exc
    role = policy.role_for(identity)
    if role is None:
        audit.record_anonymous(
            session,
            "auth.denied",
            identity.email.rsplit("@", 1)[-1],
            workspace_id=LOCAL_WORKSPACE_ID,
            decision="denied",
            details={"reason": "not_allowed", "hosted_domain": identity.hosted_domain},
        )
        await session.commit()
        raise LoginRefused("not_allowed")

    user = await _member(session, identity, role)
    token = secrets.token_urlsafe(32)
    session.add(
        AuthSession(
            user_id=user.id,
            token_hash=_hash(token),
            expires_at=datetime.now(UTC) + policy.ttl,
        )
    )
    membership = await session.get(Membership, (LOCAL_WORKSPACE_ID, user.id))
    ctx = RequestContext(
        user_id=user.id,
        workspace_ids=frozenset({LOCAL_WORKSPACE_ID}),
        default_workspace_id=LOCAL_WORKSPACE_ID,
    )
    audit.record(
        session,
        ctx,
        "auth.login",
        user.id,
        details={"role": membership.role if membership else role},
    )
    await session.commit()
    return token


async def _member(session: AsyncSession, identity: Identity, role: str) -> User:
    """Find the account by issuer + sub (or link a same-e-mail account with none), keep
    its e-mail and name current, and make sure it belongs to the local workspace."""
    user = await session.scalar(select(User).where(User.oidc_subject == identity.subject))
    if user is None:
        user = await session.scalar(
            select(User).where(User.email == identity.email, User.oidc_subject.is_(None))
        )
        if user is None:
            user = User(email=identity.email, display_name=identity.name)
            session.add(user)
        user.oidc_subject = identity.subject
    else:
        taken = await session.scalar(
            select(User.id).where(User.email == identity.email, User.id != user.id)
        )
        if taken is None:
            user.email = identity.email
    user.display_name = identity.name
    await session.flush()

    membership = await session.get(Membership, (LOCAL_WORKSPACE_ID, user.id))
    if membership is None:
        session.add(Membership(workspace_id=LOCAL_WORKSPACE_ID, user_id=user.id, role=role))
    elif role == "owner":
        membership.role = "owner"  # a listed owner is always owner
    await session.flush()
    return user


async def user_for(session: AsyncSession, token: str | None) -> str | None:
    if not token:
        return None
    found = await session.scalar(
        select(AuthSession.user_id).where(
            AuthSession.token_hash == _hash(token),
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > datetime.now(UTC),
        )
    )
    return found


async def logout(session: AsyncSession, token: str | None) -> None:
    if not token:
        return
    open_session = await session.scalar(
        select(AuthSession).where(
            AuthSession.token_hash == _hash(token), AuthSession.revoked_at.is_(None)
        )
    )
    if open_session is None:
        return
    open_session.revoked_at = datetime.now(UTC)
    ctx = RequestContext(
        user_id=open_session.user_id,
        workspace_ids=frozenset({LOCAL_WORKSPACE_ID}),
        default_workspace_id=LOCAL_WORKSPACE_ID,
    )
    audit.record(session, ctx, "auth.logout", open_session.user_id)
    await session.commit()
