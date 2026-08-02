"""Health check route.

Minimal liveness endpoint used by deployment platforms (e.g. Render) to
verify the service is up.
"""

from fastapi import APIRouter

# Liveness endpoint used by deployment platforms.
router = APIRouter(tags=["health"])


@router.get("/health")
def healthcheck() -> dict[str, str]:
    """Return the service liveness status.

    Returns:
        A dict with ``status`` set to ``"ok"``.
    """
    return {"status": "ok"}
