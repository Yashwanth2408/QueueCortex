from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_app_settings
from app.auth import SESSION_COOKIE, create_session_token, generate_otp, hash_otp, verify_session_token
from app.config import Settings
from app.db import get_session
from app.email_sender import EmailSendError, send_otp_email
from app.models import OtpCode
from app.sync.timeutil import utcnow

router = APIRouter(prefix="/auth", tags=["auth"])


class RequestOtpBody(BaseModel):
    email: EmailStr


class VerifyOtpBody(BaseModel):
    email: EmailStr
    code: str


@router.post("/request-otp")
async def request_otp(
    body: RequestOtpBody,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_app_settings),
):
    email = body.email.lower()
    if email != settings.resolved_allowed_login_email:
        raise HTTPException(403, "This app isn't set up for that email address")

    now = utcnow()
    recent = (
        await session.execute(
            select(OtpCode).where(OtpCode.email == email).order_by(OtpCode.created_at.desc()).limit(1)
        )
    ).scalar_one_or_none()
    if recent and (now - recent.created_at) < timedelta(seconds=20):
        raise HTTPException(429, "Please wait a few seconds before requesting another code")

    code = generate_otp()
    session.add(
        OtpCode(
            email=email,
            code_hash=hash_otp(code, email),
            created_at=now,
            expires_at=now + timedelta(minutes=settings.otp_ttl_minutes),
            attempts=0,
        )
    )
    await session.commit()

    try:
        await send_otp_email(settings, email, code)
        return {"sent": True, "dev_code": None}
    except EmailSendError:
        # SMTP isn't configured (or failed) - fall back to returning the code
        # directly so login isn't blocked while email delivery gets set up.
        return {"sent": False, "dev_code": code}


@router.post("/verify-otp")
async def verify_otp(
    body: VerifyOtpBody,
    response: Response,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_app_settings),
):
    email = body.email.lower()
    otp = (
        await session.execute(
            select(OtpCode)
            .where(OtpCode.email == email, OtpCode.consumed_at.is_(None))
            .order_by(OtpCode.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if otp is None:
        raise HTTPException(400, "No pending code for this email - request a new one")

    now = utcnow()
    if now > otp.expires_at:
        raise HTTPException(400, "Code expired - request a new one")
    if otp.attempts >= 5:
        raise HTTPException(429, "Too many attempts - request a new code")

    if hash_otp(body.code.strip(), email) != otp.code_hash:
        otp.attempts += 1
        await session.commit()
        raise HTTPException(400, "Incorrect code")

    otp.consumed_at = now
    await session.commit()

    token = create_session_token(email, settings.session_secret, settings.session_ttl_days)
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=settings.session_ttl_days * 24 * 3600,
        path="/",
    )
    return {"ok": True, "email": email}


@router.get("/me")
async def me(request: Request, settings: Settings = Depends(get_app_settings)):
    token = request.cookies.get(SESSION_COOKIE)
    email = verify_session_token(token, settings.session_secret)
    if not email:
        raise HTTPException(401, "Not authenticated")
    return {"email": email}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}
