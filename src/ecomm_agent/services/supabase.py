"""Supabase client factory for golden dataset.

Provides a singleton client using service_role key (server-side, bypasses RLS)
or anon key as fallback. Resolves URL from SUPABASE_URL or SUPABASE_PROJECT_ID.
"""

from __future__ import annotations

import logging

from ecomm_agent.core.config import settings

logger = logging.getLogger(__name__)

_client = None


def get_supabase_client():
    """Return a Supabase client (cached).

    Uses service_role key if available (server-side), otherwise anon key.
    Returns None when no URL or key is configured.

    Returns:
        Supabase client instance or None.
    """
    global _client
    if _client is not None:
        return _client

    url = settings.resolved_supabase_url
    key = settings.resolved_supabase_service_key or settings.supabase_anon_key

    if not url or not key:
        logger.debug("supabase not configured (missing URL or key)")
        return None

    try:
        from supabase import create_client

        _client = create_client(url, key)
        logger.info("supabase client created", extra={"url": url})
        return _client
    except Exception as exc:
        logger.warning("supabase client creation failed", extra={"error": str(exc)})
        return None


def is_supabase_configured() -> bool:
    """Whether Supabase is configured with URL and key."""
    return bool(settings.resolved_supabase_url and (settings.resolved_supabase_service_key or settings.supabase_anon_key))


def reset_supabase_client() -> None:
    """Reset cached client (useful for tests)."""
    global _client
    _client = None
