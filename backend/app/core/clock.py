from datetime import UTC, datetime


def get_now() -> datetime:
    """Current time as an aware UTC datetime. Injected as a dependency so tests can freeze it."""
    return datetime.now(UTC)
