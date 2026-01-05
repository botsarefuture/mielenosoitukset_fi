from flask import g, has_request_context, request, session
from flask_caching import Cache
from flask_login import current_user

from config import Config

cache = Cache(
    config={
        "CACHE_TYPE": Config.CACHE_TYPE,
        "CACHE_REDIS_HOST": Config.CACHE_REDIS_HOST,
        "CACHE_REDIS_PORT": Config.CACHE_REDIS_PORT,
        "CACHE_REDIS_DB": Config.CACHE_REDIS_DB,
        "CACHE_DEFAULT_TIMEOUT": Config.CACHE_DEFAULT_TIMEOUT,
    }
)


def _has_pending_flashes():
    """
    Detect if there are flash messages queued for this request/session.
    Returns True if the current request has flashed (tracks via `g`) or the
    session still contains pending flashes (e.g. after a redirect).
    """
    if not has_request_context():
        return False
    if getattr(g, "_has_flash_messages", False):
        return True
    flashes = session.get("_flashes")
    return bool(flashes)


def should_skip_cache(public_only=True):
    """
    Global helper to decide whether response caching should be skipped.
    Parameters
    ----------
    public_only : bool, optional
        When True (default) authenticated sessions bypass cached responses.
        When False the caller manages cache isolation (e.g., per-user keys) and
        only force_reload/flash checks disable caching.

    We bypass caches when:
      - outside a request context
      - there are active/pending flash messages
      - ?force_reload=1 is present in the query string (manual bypass)
      - the requester is authenticated (only when `public_only=True`)
    """
    if not has_request_context():
        return False

    if request.args.get("force_reload"):
        return True

    if _has_pending_flashes():
        return True

    if public_only:
        try:
            if current_user.is_authenticated:
                return True
        except Exception:
            # current_user may not be ready outside an app context
            pass

    return False


def skip_cache_public_only(*args, **kwargs):
    """Wrapper for cache decorators where authenticated users should bypass."""
    return should_skip_cache(public_only=True)


def skip_cache_even_authenticated(*args, **kwargs):
    """Wrapper for cache decorators where authenticated users may still cache."""
    return should_skip_cache(public_only=False)
