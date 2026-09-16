from pydantic import BaseModel, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    company_email: EmailStr
    company_name: str | None = Field(default=None, min_length=2, max_length=160)
    password: str = Field(min_length=8, max_length=72)
    confirm_password: str = Field(min_length=8, max_length=72)
    company_website: str | None = Field(default=None, max_length=255)
    industry: str | None = Field(default=None, max_length=120)
    company_size: str | None = Field(default=None, max_length=50)

    @field_validator("full_name", "company_name")
    @classmethod
    def trim_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None

    @field_validator("confirm_password")
    @classmethod
    def passwords_must_match(cls, value: str, info) -> str:
        if info.data.get("password") != value:
            raise ValueError("Passwords do not match")
        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: str
    full_name: str
    email: EmailStr
    company_id: str
    company_name: str
    role: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
