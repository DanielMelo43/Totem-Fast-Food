import hashlib
import hmac
import secrets
import threading
import time
from collections import defaultdict, deque

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import settings
from .database import connect, transaction

_attempts: dict[str, deque[float]] = defaultdict(deque)
_lock = threading.Lock()
_bearer = HTTPBearer(auto_error=False)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def check_login_limit(ip: str) -> None:
    now = time.monotonic()
    with _lock:
        attempts = _attempts[ip]
        while attempts and now - attempts[0] >= 60:
            attempts.popleft()
        if len(attempts) >= 10:
            retry = max(1, int(60 - (now - attempts[0])))
            raise HTTPException(429, "Muitas tentativas. Tente novamente em instantes.", headers={"Retry-After": str(retry)})
        attempts.append(now)


def clear_login_attempts(ip: str) -> None:
    with _lock:
        _attempts.pop(ip, None)


def authenticate(username: str, password: str) -> bool:
    return hmac.compare_digest(username, settings.admin_username) and hmac.compare_digest(password, settings.admin_password)


def create_token() -> str:
    token = secrets.token_urlsafe(32)
    expires_at = int(time.time()) + 8 * 60 * 60
    with transaction() as db:
        db.execute("DELETE FROM auth_tokens WHERE expires_at <= %s", (int(time.time()),))
        db.execute("INSERT INTO auth_tokens (token_hash, expires_at) VALUES (%s, %s)", (_digest(token), expires_at))
    return token


def require_admin(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> None:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Autenticação necessária")
    with connect() as db:
        row = db.execute(
            "SELECT 1 FROM auth_tokens WHERE token_hash = %s AND expires_at > %s",
            (_digest(credentials.credentials), int(time.time())),
        ).fetchone()
    if not row:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Credenciais inválidas")
