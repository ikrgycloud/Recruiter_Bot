import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select

from app.api.dependencies import DbSession, get_current_user
from app.core.config import settings
from app.core.token_store import decrypt_token
from app.models.company import Company
from app.models.email_message import EmailMessage
from app.models.google_connection import GoogleConnection
from app.models.outlook_connection import OutlookConnection
from app.models.user import User
from app.services.google_workspace import credentials_from_connection, run_sync

router = APIRouter()


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


def _normalize_permissions(raw: str | None) -> list[str]:
    if not raw:
        return []
    if isinstance(raw, str):
        values = raw.split()
    elif isinstance(raw, (list, tuple, set)):
        values = [str(item) for item in raw]
    else:
        values = [str(raw)]
    cleaned = []
    for item in values:
        trimmed = item.strip()
        if trimmed:
            cleaned.append(trimmed)
    return cleaned


def _permission_summary(token_json: str | None) -> list[str]:
    if not token_json:
        return []
    try:
        raw = decrypt_token(token_json)
        payload = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    scopes = payload.get("scope") or payload.get("scopes") or []
    values = _normalize_permissions(scopes)
    if values:
        return values
    token_data = payload.get("token") or {}
    if isinstance(token_data, dict):
        return _normalize_permissions(token_data.get("scope") or token_data.get("scopes"))
    return []


@router.get("/overview")
async def overview(session: DbSession, user: User = Depends(get_current_user)) -> dict:
    email_count = await session.scalar(select(func.count(EmailMessage.id)).where(EmailMessage.user_id == user.id))
    reschedule_count = await session.scalar(select(func.count(EmailMessage.id)).where(
        EmailMessage.user_id == user.id, EmailMessage.classification == "reschedule_request"))
    connection = await session.scalar(select(GoogleConnection).where(GoogleConnection.user_id == user.id))
    google_connected = False
    if connection:
        try:
            _, refreshed = await run_sync(credentials_from_connection, connection)
            if refreshed:
                await session.commit()
            google_connected = True
        except ValueError:
            google_connected = False
    return {
        "user": {"id": str(user.id), "full_name": user.full_name, "email": user.email,
                 "company_id": str(user.company_id), "role": user.role},
        "metrics": {"email_count": email_count or 0, "reschedule_count": reschedule_count or 0},
        "google_connected": google_connected,
    }


@router.get("/admin/overview")
async def admin_overview(session: DbSession, user: User = Depends(require_admin)) -> dict[str, Any]:
    company = await session.get(Company, user.company_id)
    # The configured system administrator has global directory access. Other
    # admin accounts remain restricted to their own company workspace.
    if user.email.lower() == settings.admin_email.lower():
        member_rows = await session.scalars(select(User).order_by(User.created_at.desc()))
    else:
        member_rows = await session.scalars(
            select(User).where(User.company_id == user.company_id).order_by(User.created_at.desc())
        )
    members = member_rows.all()

    users: list[dict[str, Any]] = []
    alerts: list[dict[str, Any]] = []
    approvals: list[dict[str, Any]] = []
    google_connected = 0
    outlook_connected = 0
    granted_permissions: set[str] = set()

    for member in members:
        google_connection = await session.scalar(select(GoogleConnection).where(GoogleConnection.user_id == member.id))
        outlook_connection = await session.scalar(select(OutlookConnection).where(OutlookConnection.user_id == member.id))
        permissions = []
        if google_connection:
            google_connected += 1
            permissions.extend(_permission_summary(google_connection.token_json))
        if outlook_connection:
            outlook_connected += 1
            permissions.extend(_permission_summary(outlook_connection.token_json))

        unique_permissions = []
        seen: set[str] = set()
        for permission in permissions:
            if permission not in seen:
                seen.add(permission)
                unique_permissions.append(permission)
        for permission in unique_permissions:
            granted_permissions.add(permission)

        row = {
            "id": str(member.id),
            "full_name": member.full_name,
            "email": member.email,
            "role": member.role,
            "status": "active" if member.is_active else "inactive",
            "google_connected": google_connection is not None,
            "outlook_connected": outlook_connection is not None,
            "permission_count": len(unique_permissions),
            "permissions": unique_permissions[:10],
            "approval_state": "approved" if google_connection or outlook_connection else "needs_setup",
            "last_updated": (google_connection.updated_at if google_connection else outlook_connection.updated_at if outlook_connection else member.created_at).isoformat() if (google_connection or outlook_connection or member.created_at) else None,
        }
        users.append(row)

        if not google_connection and not outlook_connection:
            alerts.append({
                "type": "connectivity",
                "title": f"{member.full_name} has no active integrations",
                "severity": "medium",
                "message": "This user has not connected Google or Outlook yet.",
            })
        elif not google_connection:
            alerts.append({
                "type": "google_missing",
                "title": f"{member.full_name} is missing Google access",
                "severity": "medium",
                "message": "Google Workspace access is required for Gmail and Calendar workflows.",
            })
        elif not outlook_connection:
            alerts.append({
                "type": "outlook_missing",
                "title": f"{member.full_name} is missing Outlook access",
                "severity": "low",
                "message": "Outlook integration is not configured for this user.",
            })

        if google_connection or outlook_connection:
            approvals.append({
                "user": member.full_name,
                "email": member.email,
                "role": member.role,
                "status": "approved",
                "systems": [
                    "Google Workspace" if google_connection else None,
                    "Microsoft Outlook" if outlook_connection else None,
                ],
            })

    if not alerts:
        alerts.append({
            "type": "system",
            "title": "All user integrations are healthy",
            "severity": "info",
            "message": "No immediate remediation is required across the company workspace.",
        })

    return {
        "company": {
            "id": str(company.id) if company else None,
            "name": company.name if company else "Workspace",
            "total_users": len(members),
            "admins": sum(1 for member in members if member.role == "admin"),
            "recruiters": sum(1 for member in members if member.role == "recruiter"),
        },
        "summary": {
            "total_users": len(members),
            "google_connected": google_connected,
            "outlook_connected": outlook_connected,
            "integration_coverage": round((google_connected + outlook_connected) / len(members) * 100, 2) if members else 0,
            "permission_count": len(granted_permissions),
            "approval_count": len(approvals),
        },
        "systems": {
            "google": {
                "connected_users": google_connected,
                "required_scopes": [
                    "https://www.googleapis.com/auth/gmail.readonly",
                    "https://www.googleapis.com/auth/gmail.send",
                    "https://www.googleapis.com/auth/calendar",
                ],
            },
            "outlook": {
                "connected_users": outlook_connected,
                "required_scopes": [
                    "Mail.Read",
                    "Mail.Send",
                    "Calendars.ReadWrite",
                    "offline_access",
                ],
            },
        },
        "users": users,
        "alerts": alerts[:8],
        "approvals": approvals[:10],
    }


@router.get("/notifications")
async def notifications(session: DbSession, user: User = Depends(get_current_user)) -> list[dict[str, Any]]:
    """Return accepted reschedule approvals for the recruiter workspace."""
    records = await session.scalars(select(EmailMessage).where(
        EmailMessage.user_id == user.id,
        EmailMessage.classification == "reschedule_request",
        EmailMessage.processed.is_(True),
    ).order_by(EmailMessage.created_at.desc()).limit(50))
    return [{
        "id": str(message.id),
        "type": "reschedule_accepted",
        "title": "Interview reschedule accepted",
        "sender": message.sender,
        "subject": message.subject or "Interview reschedule request",
        "received_at": message.received_at.isoformat() if message.received_at else None,
        "recorded_at": message.created_at.isoformat() if message.created_at else None,
    } for message in records.all()]
