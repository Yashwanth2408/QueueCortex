"""Single-user email+OTP auth. Sessions are stateless signed tokens (HMAC-SHA256
over an {email, exp} payload) held in an httpOnly cookie - no server-side
session table needed; logout just clears the cookie."""

import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta

from app.sync.timeutil import utcnow

SESSION_COOKIE = "qc_session"


def generate_otp() -> str:
    return f"{secrets.randbelow(10000):04d}"


def hash_otp(code: str, email: str) -> str:
    return hashlib.sha256(f"{email.lower()}:{code}".encode()).hexdigest()


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    padding = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + padding)


def create_session_token(email: str, secret: str, ttl_days: int) -> str:
    payload = {"email": email, "exp": (utcnow() + timedelta(days=ttl_days)).isoformat()}
    payload_b64 = _b64url_encode(json.dumps(payload).encode())
    sig = hmac.new(secret.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{sig}"


def verify_session_token(token: str | None, secret: str) -> str | None:
    if not token or "." not in token:
        return None
    payload_b64, sig = token.rsplit(".", 1)
    expected_sig = hmac.new(secret.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected_sig):
        return None
    try:
        payload = json.loads(_b64url_decode(payload_b64))
        exp = datetime.fromisoformat(payload["exp"])
    except (ValueError, KeyError, json.JSONDecodeError):
        return None
    if utcnow() > exp:
        return None
    return payload.get("email")
