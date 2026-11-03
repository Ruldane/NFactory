from fastapi import APIRouter

from app.schemas.common import Items
from app.schemas.runs import RecipeOut
from nfactory_core.catalog import CATALOG

router = APIRouter(prefix="/recipes", tags=["recipes"])


@router.get("")
async def list_recipes() -> Items[RecipeOut]:
    """Every project type, built or planned. Planned ones carry their phase."""
    return Items(
        items=[
            RecipeOut(
                kind=entry.kind,
                project_type=entry.project_type,
                label=entry.label,
                description=entry.description,
                deliverable=entry.deliverable,
                outputs=list(entry.outputs),
                phase=entry.phase,
                available=entry.available,
            )
            for entry in CATALOG
        ]
    )
