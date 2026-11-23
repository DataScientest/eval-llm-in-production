"""Request ID middleware - Exercise 3 (starting point).

TODO Exercise 3: give every request an ID and propagate it.
- Generate an ID (or reuse the incoming X-Request-ID header).
- Store it in a contextvars.ContextVar so that log records can read it.
- Return it in the X-Request-ID response header.
- Register the middleware in config/app.py.
See docs/EXAM.md, Exercise 3.
"""

from contextvars import ContextVar

from fastapi import Request

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


async def request_id_middleware(request: Request, call_next):
    # TODO Exercise 3: set request_id_var, call the next handler, add the X-Request-ID header
    return await call_next(request)
