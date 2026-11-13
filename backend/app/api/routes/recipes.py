from fastapi import APIRouter, Query

from app.api.deps import DB, CurrentHousehold
from app.models.enums import MealType
from app.schemas.recipe import MissingOut, MissingRequest, RecipeOut, RecommendationsOut
from app.services import recipe_service as svc
from app.services.mappers import missing_out, recipe_out

router = APIRouter(prefix="/recipes", tags=["Tarifler & Öneri"])


@router.get("", response_model=list[RecipeOut])
def list_recipes(db: DB, meal_type: MealType | None = None):
    return [recipe_out(r) for r in svc.list_recipes(db, meal_type)]


@router.get("/recommendations", response_model=RecommendationsOut)
def recommendations(
    db: DB,
    household: CurrentHousehold,
    meal_type: MealType | None = None,
    servings: int | None = Query(default=None, ge=1, le=50),
    limit: int = Query(default=8, ge=1, le=30),
    ai: bool = False,
):
    """'Buzdolabında ne var?' — evdeki (özellikle bozulmaya yakın) ürünleri kullanan tarifler."""
    return svc.recommendations(db, household, meal_type=meal_type, servings=servings, limit=limit, use_ai=ai)


@router.post("/missing", response_model=MissingOut)
def missing(data: MissingRequest, db: DB, household: CurrentHousehold):
    """Seçili tarifler ve/veya plan aralığı için envanterde olmayan malzemeler."""
    lines = svc.missing_for(db, household, data.selections, data.plan_from, data.plan_to)
    return MissingOut(lines=[missing_out(m) for m in lines])


@router.get("/{recipe_id}", response_model=RecipeOut)
def get_recipe(recipe_id: int, db: DB):
    return recipe_out(svc.get_recipe(db, recipe_id))
