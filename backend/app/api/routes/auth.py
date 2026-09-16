from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.dependencies import DbSession
from app.core.security import create_access_token, hash_password, verify_password
from app.models.company import Company
from app.models.user import User
from app.schemas.auth import AuthResponse, LoginRequest, RegisterRequest, UserResponse

router = APIRouter()


def user_response(user: User, company: Company) -> UserResponse:
    return UserResponse(id=str(user.id), full_name=user.full_name, email=user.email,
                        company_id=str(company.id), company_name=company.name, role=user.role)


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, session: DbSession) -> AuthResponse:
    email = str(payload.company_email).lower().strip()
    domain = email.rsplit("@", 1)[-1]
    if await session.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=409, detail="An account already exists for this email")

    company_name = payload.company_name or f"{domain} account"
    company = Company(name=company_name, website=payload.company_website,
                      industry=payload.industry, size=payload.company_size)
    user = User(company=company, full_name=payload.full_name, email=email,
                password_hash=hash_password(payload.password), role="recruiter")
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return AuthResponse(access_token=create_access_token(str(user.id)), user=user_response(user, company))


@router.post("/login", response_model=AuthResponse)
async def login(payload: LoginRequest, session: DbSession) -> AuthResponse:
    user = await session.scalar(select(User).where(User.email == str(payload.email).lower()))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    company = await session.get(Company, user.company_id)
    return AuthResponse(access_token=create_access_token(str(user.id)), user=user_response(user, company))
