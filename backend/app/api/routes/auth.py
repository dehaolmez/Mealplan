from fastapi import APIRouter, Request, Response, status
from fastapi.responses import PlainTextResponse

from app.api.deps import DB, SESSION_COOKIE, CurrentUser
from app.core.config import get_settings
from app.legal import LEGAL_VERSION, read_document
from app.schemas.auth import (
    AuthConfigOut,
    ConsentIn,
    ForgotIn,
    GoogleLoginIn,
    JoinIn,
    LoginIn,
    MeOut,
    PasswordChangeIn,
    RegisterIn,
    ResetIn,
)
from app.services import auth_service as svc
from app.services import rate_limit
from app.services.errors import BadRequest, NotFound

router = APIRouter(prefix="/auth", tags=["Hesap & KVKK"])
legal_router = APIRouter(prefix="/legal", tags=["Hesap & KVKK"])


def _set_session(response: Response, token: str) -> None:
    s = get_settings()
    response.set_cookie(
        SESSION_COOKIE, token, max_age=s.session_days * 86400, httponly=True, secure=s.cookie_secure,
        samesite="lax", path="/",
    )


def _limit(request: Request, key: str, limit: int = 10, window_s: int = 900) -> None:
    ip = request.client.host if request.client else "?"
    if not rate_limit.allow(f"{key}:{ip}", limit, window_s):
        raise BadRequest("Çok fazla deneme yapıldı. Lütfen birkaç dakika sonra tekrar deneyin.")


@router.get("/config", response_model=AuthConfigOut)
def config():
    return AuthConfigOut(google_client_id=get_settings().google_client_id or None, legal_version=LEGAL_VERSION)


@router.post("/register", response_model=MeOut, status_code=status.HTTP_201_CREATED)
def register(data: RegisterIn, request: Request, response: Response, db: DB):
    _limit(request, "register", 5, 3600)
    user = svc.register(db, data)
    _set_session(response, svc.issue_session(user))
    return svc.me(db, user)


@router.post("/login", response_model=MeOut)
def login(data: LoginIn, request: Request, response: Response, db: DB):
    _limit(request, f"login:{data.email.lower()}", 8, 900)
    user = svc.login(db, data.email, data.password)
    _set_session(response, svc.issue_session(user))
    return svc.me(db, user)


@router.post("/google", response_model=MeOut)
def google(data: GoogleLoginIn, request: Request, response: Response, db: DB):
    _limit(request, "google", 20, 900)
    user, _created = svc.login_google(db, data)
    _set_session(response, svc.issue_session(user))
    return svc.me(db, user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response):
    response.delete_cookie(SESSION_COOKIE, path="/")


@router.get("/me", response_model=MeOut)
def me(user: CurrentUser, db: DB):
    return svc.me(db, user)


@router.post("/me/accept-terms", response_model=MeOut)
def accept_terms(user: CurrentUser, db: DB):
    svc.accept_current_terms(db, user)
    return svc.me(db, user)


@router.post("/me/consents", response_model=MeOut)
def set_consent(data: ConsentIn, user: CurrentUser, db: DB):
    """Açık rızayı ver/geri çek. Sağlık verisi rızası geri çekilirse bireyler, konum rızası geri çekilirse
    ev konumu silinir."""
    svc.set_consent(db, user, data.kind, data.granted)
    return svc.me(db, user)


@router.post("/me/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(data: PasswordChangeIn, user: CurrentUser, db: DB, response: Response):
    svc.change_password(db, user, data.current_password, data.new_password)
    _set_session(response, svc.issue_session(user))


@router.post("/forgot", status_code=status.HTTP_204_NO_CONTENT)
def forgot(data: ForgotIn, request: Request, db: DB):
    _limit(request, "forgot", 5, 3600)
    svc.forgot_password(db, data.email)


@router.post("/reset", response_model=MeOut)
def reset(data: ResetIn, response: Response, db: DB):
    user = svc.reset_password(db, data.token, data.new_password)
    _set_session(response, svc.issue_session(user))
    return svc.me(db, user)


@router.post("/verify", status_code=status.HTTP_204_NO_CONTENT)
def verify(token: str, db: DB):
    svc.verify_email(db, token)


@router.post("/me/resend-verification", status_code=status.HTTP_204_NO_CONTENT)
def resend_verification(user: CurrentUser, request: Request):
    _limit(request, f"verify:{user.id}", 3, 3600)
    svc.send_verification(user)


@router.post("/me/household/join", response_model=MeOut)
def join(data: JoinIn, user: CurrentUser, db: DB):
    svc.join_household(db, user, data.invite_code)
    return svc.me(db, user)


@router.post("/me/household/invite", response_model=MeOut)
def rotate_invite(user: CurrentUser, db: DB):
    svc.rotate_invite(db, user)
    return svc.me(db, user)


@router.get("/me/export")
def export(user: CurrentUser, db: DB):
    """KVKK m.11: verilerimin dökümü (JSON)."""
    return svc.export_data(db, user)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_me(user: CurrentUser, db: DB, response: Response):
    svc.delete_account(db, user)
    response.delete_cookie(SESSION_COOKIE, path="/")


@legal_router.get("/{slug}", response_class=PlainTextResponse)
def legal_document(slug: str):
    text = read_document(slug)
    if text is None:
        raise NotFound("Belge", slug)
    return PlainTextResponse(text, media_type="text/markdown; charset=utf-8")
