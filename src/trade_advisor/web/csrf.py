from __future__ import annotations

import secrets
from typing import Any

from itsdangerous import BadSignature, Signer
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})
CSRF_COOKIE = "csrf_token"
CSRF_HEADER = "x-csrf-token"
CSRF_FORM_FIELD = "csrf_token"
_TOKEN_ATTR = "_csrf_token"


class CSRFMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: Any, secret_key: str, cookie_secure: bool = False, cookie_samesite: str = "Lax") -> None:
        super().__init__(app)
        self._signer = Signer(secret_key)
        self._cookie_secure = cookie_secure
        self._cookie_samesite = cookie_samesite

    def _sign(self, raw: str) -> str:
        return self._signer.sign(raw).decode()

    def _verify(self, token: str) -> bool:
        try:
            self._signer.unsign(token)
            return True
        except BadSignature:
            return False

    def _get_or_create_token(self, request: Request) -> str:
        existing: str | None = getattr(request.state, _TOKEN_ATTR, None)
        if existing is not None:
            return existing
        raw = secrets.token_hex(32)
        signed = self._sign(raw)
        setattr(request.state, _TOKEN_ATTR, signed)
        return signed

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method in SAFE_METHODS:
            token = self._get_or_create_token(request)
            response = await call_next(request)
            if CSRF_COOKIE not in request.cookies:
                response.set_cookie(
                    CSRF_COOKIE,
                    token,
                    httponly=False,
                    secure=self._cookie_secure,
                    samesite=self._cookie_samesite,  # type: ignore[arg-type]
                    path="/",
                    max_age=60 * 60 * 24 * 365,
                )
            return response

        cookie_token = request.cookies.get(CSRF_COOKIE)
        header_token = request.headers.get(CSRF_HEADER)

        submitted: str | None
        if header_token:
            submitted = header_token
        elif request.headers.get("content-type", "").startswith("application/x-www-form-urlencoded"):
            form_data = await request.form()
            raw_val = form_data.get(CSRF_FORM_FIELD, None)
            submitted = raw_val if isinstance(raw_val, str) else None
        else:
            submitted = None

        if not cookie_token or not submitted:
            return Response("CSRF token missing", status_code=403)

        if not self._verify(cookie_token) or not self._verify(submitted):
            return Response("Invalid CSRF token", status_code=403)

        if cookie_token != submitted:
            return Response("CSRF token mismatch", status_code=403)

        return await call_next(request)
