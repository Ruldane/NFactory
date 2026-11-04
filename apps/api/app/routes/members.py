"""A member's rights (ADR-0015): export one's own data; an admin lists and erases members."""

from fastapi import APIRouter
from fastapi.responses import Response

from app.context import CanConfigure, Context, Session
from app.schemas.common import Items
from app.schemas.members import ErasureOut, MemberOut
from app.services import audit, member_rights

router = APIRouter(tags=["members"])

EXPORT_FILENAME = "nfactory-mes-donnees.json"


@router.get("/me/export")
async def export_my_data(session: Session, ctx: Context) -> Response:
    """Everything NFactory links to the caller, as a JSON file (GDPR art. 15 and 20)."""
    data = await member_rights.export_data(session, ctx.user_id)
    audit.record(session, ctx, "member.export", ctx.user_id)
    await session.commit()
    return Response(
        content=data.model_dump_json(indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{EXPORT_FILENAME}"'},
    )


@router.get("/members")
async def list_members(session: Session, ctx: CanConfigure) -> Items[MemberOut]:
    return Items(items=await member_rights.members(session, ctx))


@router.delete("/members/{user_id}")
async def erase_member(user_id: str, session: Session, ctx: CanConfigure) -> ErasureOut:
    """Remove the member from this workspace; anonymise them if none is left (art. 17)."""
    result = await member_rights.erase(session, ctx, user_id)
    audit.record(session, ctx, "member.erased", user_id, details={"anonymised": result.anonymised})
    await session.commit()
    return result
