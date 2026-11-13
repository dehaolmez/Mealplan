from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import ConsentKind, HouseholdRole


class ConsentIn(BaseModel):
    kind: ConsentKind
    granted: bool


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(default="", max_length=80)
    accept_terms: bool
    acknowledge_privacy_notice: bool
    health_data_consent: bool = False
    location_consent: bool = False
    ai_transfer_consent: bool = False
    marketing_consent: bool = False
    with_sample_data: bool = True
    invite_code: str | None = None


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)


class GoogleLoginIn(BaseModel):
    credential: str
    # Yalnız ilk girişte (hesap oluşturulurken) gerekli
    accept_terms: bool = False
    acknowledge_privacy_notice: bool = False
    health_data_consent: bool = False
    location_consent: bool = False
    ai_transfer_consent: bool = False
    with_sample_data: bool = True


class PasswordChangeIn(BaseModel):
    current_password: str | None = None
    new_password: str = Field(min_length=8, max_length=128)


class ForgotIn(BaseModel):
    email: EmailStr


class ResetIn(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class JoinIn(BaseModel):
    invite_code: str = Field(min_length=6, max_length=16)


class ConsentState(BaseModel):
    kind: ConsentKind
    granted: bool
    text_version: str | None
    updated_at: datetime | None


class MeOut(BaseModel):
    id: int
    email: str
    display_name: str
    email_verified: bool
    has_password: bool
    google_linked: bool
    household_id: int
    household_name: str
    role: HouseholdRole
    invite_code: str | None
    consents: list[ConsentState]
    legal_version: str
    needs_reconsent: bool


class AuthConfigOut(BaseModel):
    google_client_id: str | None
    legal_version: str
