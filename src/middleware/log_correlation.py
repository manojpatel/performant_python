import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

# ContextVar to store the request ID for valid access across async context
# Defaults to None
request_id_ctx: ContextVar[str] = ContextVar("request_id", default=None)


class RequestIdMiddleware(BaseHTTPMiddleware):
    """
    Middleware that ensures every request has a unique ID.

    1. Checks for X-Request-ID header.
    2. If missing, generates a new UUID.
    3. Stores it in a ContextVar for logging.
    4. Adds it to the response headers.
    """

    async def dispatch(self, request: Request, call_next):
        # 1. Get or generate ID
        req_id = request.headers.get("X-Request-ID")
        if not req_id:
            req_id = str(uuid.uuid4())

        # 2. Set ContextVar
        token = request_id_ctx.set(req_id)

        try:
            # 3. Process Request
            response = await call_next(request)

            # 4. Add to Response
            response.headers["X-Request-ID"] = req_id
            return response

        finally:
            # Cleanup ContextVar
            request_id_ctx.reset(token)


def get_request_id() -> str | None:
    """Helper to get the current request ID."""
    return request_id_ctx.get()
