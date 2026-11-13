from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Household, User
from app.services import auth_service

DB = Annotated[Session, Depends(get_db)]
SESSION_COOKIE = "mb_session"


def _token(request: Request) -> str | None:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):  # mobil/APK istemcileri için
        return auth[7:].strip()
    return request.cookies.get(SESSION_COOKIE)


def current_user(request: Request, db: DB) -> User:
    return auth_service.user_from_token(db, _token(request))


CurrentUser = Annotated[User, Depends(current_user)]


def current_household(user: CurrentUser, db: DB) -> Household:
    return db.get(Household, auth_service.membership(user).household_id)


CurrentHousehold = Annotated[Household, Depends(current_household)]
