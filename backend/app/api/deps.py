from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Household
from app.services import household_service

DB = Annotated[Session, Depends(get_db)]


def current_household(db: DB) -> Household:
    # Kimlik doğrulama eklendiğinde burada oturumdaki kullanıcının hanesi çözülecek.
    return household_service.get_household(db)


CurrentHousehold = Annotated[Household, Depends(current_household)]
