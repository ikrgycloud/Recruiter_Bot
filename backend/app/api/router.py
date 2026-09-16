from fastapi import APIRouter

from app.api.routes import auth, agents, integrations, portal

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(agents.router, prefix="/agents", tags=["agents"])
api_router.include_router(integrations.router, prefix="/integrations", tags=["integrations"])
api_router.include_router(portal.router, prefix="/portal", tags=["portal"])
