from datetime import date

from pydantic import BaseModel, Field

from app.domain.shelf_life import ExpiryStatus
from app.models.enums import StorageLocation
from app.schemas.catalog import IngredientOut


class InventoryItemIn(BaseModel):
    ingredient_id: int
    location: StorageLocation = StorageLocation.fridge
    quantity: float = Field(gt=0)
    unit: str | None = Field(default=None, description="g, kg, ml, l, adet. Boşsa temel birim.")
    expiry_date: date | None = Field(default=None, description="Etiketteki SKT. Boşsa raf ömrü kuralından tahmin edilir.")
    added_on: date | None = None
    opened: bool = False


class InventoryItemUpdate(BaseModel):
    quantity: float | None = Field(default=None, ge=0)
    unit: str | None = None
    expiry_date: date | None = None
    opened: bool | None = None
    location: StorageLocation | None = None


class InventoryItemOut(BaseModel):
    id: int
    ingredient: IngredientOut
    location: StorageLocation
    quantity: float
    quantity_label: str
    added_on: date
    expiry_date: date
    expiry_estimated: bool
    opened: bool
    days_left: int
    status: ExpiryStatus


class ExpiryAlert(BaseModel):
    item_id: int
    ingredient_name: str
    emoji: str
    location: StorageLocation
    days_left: int
    status: ExpiryStatus
    message: str


class AlertsOut(BaseModel):
    expired: int
    critical: int
    warning: int
    alerts: list[ExpiryAlert]
