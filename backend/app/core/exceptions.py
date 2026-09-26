from fastapi import Request
from fastapi.responses import JSONResponse


class DomainError(Exception):
    """A 4xx carrying a machine-readable `code`. Clients key off `code`, never the message (spec §8).

    `extra` merges additional, endpoint-specific keys into the body (e.g. `fields` on
    `MISSING_REQUIRED_FIELD`, `waitlist_available` on `EVENT_FULL`) without every caller of
    every other DomainError needing to know about them.
    """

    def __init__(self, status_code: int, code: str, **extra: object) -> None:
        super().__init__(code)
        self.status_code = status_code
        self.code = code
        self.extra = extra


async def domain_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, DomainError)
    return JSONResponse(status_code=exc.status_code, content={"code": exc.code, **exc.extra})
