from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.api.deps import DB, CurrentHousehold, CurrentUser, OptionalHousehold
from app.core.config import get_settings
from app.models.enums import ConsentKind, MealType
from app.schemas.recipe import MissingOut, MissingRequest, RecipeOut, RecommendationsOut
from app.services import auth_service, gemini, rate_limit, recipe_ai
from app.services import recipe_service as svc
from app.services.errors import BadRequest
from app.services.mappers import missing_out, recipe_out

router = APIRouter(prefix="/recipes", tags=["Tarifler & Öneri"])


@router.get("", response_model=list[RecipeOut])
def list_recipes(db: DB, household: OptionalHousehold, meal_type: MealType | None = None):
    return [recipe_out(r) for r in svc.list_recipes(db, meal_type, household)]


@router.get("/recommendations", response_model=RecommendationsOut)
def recommendations(
    db: DB,
    household: CurrentHousehold,
    user: CurrentUser,
    meal_type: MealType | None = None,
    servings: int | None = Query(default=None, ge=1, le=50),
    limit: int = Query(default=8, ge=1, le=30),
    ai: bool = False,
):
    """'Buzdolabında ne var?' — evdeki (özellikle bozulmaya yakın) ürünleri kullanan tarifler."""
    consent = auth_service.has_consent(db, user, ConsentKind.ai_transfer) if ai else False
    return svc.recommendations(db, household, meal_type=meal_type, servings=servings, limit=limit, use_ai=ai,
                               ai_consent=consent)


@router.post("/missing", response_model=MissingOut)
def missing(data: MissingRequest, db: DB, household: CurrentHousehold):
    """Seçili tarifler ve/veya plan aralığı için envanterde olmayan malzemeler."""
    lines = svc.missing_for(db, household, data.selections, data.plan_from, data.plan_to, data.plan_dates)
    return MissingOut(lines=[missing_out(m) for m in lines])


class GenerateRecipeIn(BaseModel):
    meal_type: MealType | None = None
    wish: str | None = Field(default=None, max_length=200)


@router.post("/generate", response_model=RecipeOut, status_code=201)
def generate_recipe(data: GenerateRecipeIn, db: DB, household: CurrentHousehold, user: CurrentUser):
    """Gemini, evdeki (önce bozulacak) malzemelerle ve hanenin diyet kurallarıyla yeni bir tarif yazar.
    Tarif yalnız bu haneye görünür."""
    s = get_settings()
    if not s.ai_available or s.ai_provider != "gemini":
        raise BadRequest("Tarif üretimi için Gemini yapılandırılmamış")
    if not auth_service.has_consent(db, user, ConsentKind.ai_transfer):
        raise BadRequest("Tarif üretimi için Profil › Gizlilik bölümünden yapay zekâ iznini açmalısınız")
    if not rate_limit.allow(f"recipe-gen:{household.id}", 15, 3600):
        raise BadRequest("Saatte en fazla 15 tarif üretilebilir")
    try:
        recipe = recipe_ai.generate_for_household(db, household, data.meal_type.value if data.meal_type else None, data.wish)
    except gemini.GeminiError as exc:
        raise BadRequest(str(exc)) from exc
    return recipe_out(recipe)


@router.get("/{recipe_id}", response_model=RecipeOut)
def get_recipe(recipe_id: int, db: DB, household: OptionalHousehold):
    return recipe_out(svc.get_recipe(db, recipe_id, household))
