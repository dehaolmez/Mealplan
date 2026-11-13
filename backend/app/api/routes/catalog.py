from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import DB
from app.models import Ingredient
from app.schemas.catalog import IngredientOut
from app.schemas.planning import StoreOut
from app.services import pricing_service

router = APIRouter(tags=["Katalog"])


@router.get("/ingredients", response_model=list[IngredientOut])
def list_ingredients(db: DB, q: str | None = None):
    stmt = select(Ingredient).order_by(Ingredient.name)
    if q:
        stmt = stmt.where(Ingredient.name.ilike(f"%{q.strip()}%"))
    return db.scalars(stmt).all()


@router.get("/stores", response_model=list[StoreOut])
def list_stores(db: DB):
    return pricing_service.list_stores(db)
