"""API key authentication.

Disabled by default (AUTH_ENABLED=false) so local development and the hackathon
demo are never blocked by auth. When enabled, every request must send a
matching `X-API-Key` header.

`verify_api_key` is the original, single-shared-key check used by every
existing router. `require_coordinator` is additive (D9): it distinguishes a
human coordinator from n8n/AI automation using two separate static keys, and
is used only by endpoints — like recommendation approval — where the caller's
identity is itself part of the business rule (`approved_by` must never be
trusted from the request body). `verify_any_api_key` accepts any of the
three configured keys, for plan/disruption submissions any authenticated
caller (n8n, AI, or a coordinator) may make.
"""

from fastapi import Depends, Header, HTTPException, status

from app.core.config import Settings, get_settings

COORDINATOR_IDENTITY = "coordinator"


def verify_api_key(
    x_api_key: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    if not settings.auth_enabled:
        return
    if x_api_key is None or x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid API key.",
        )


def verify_any_api_key(
    x_api_key: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    if not settings.auth_enabled:
        return
    accepted = {
        key
        for key in (settings.api_key, settings.coordinator_api_key, settings.automation_api_key)
        if key
    }
    if x_api_key is None or x_api_key not in accepted:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid API key.",
        )


def require_coordinator(
    x_api_key: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> str:
    """Resolves the authenticated actor for coordinator-only actions.

    Returns a fixed identity string ("coordinator") rather than an arbitrary
    caller-supplied name — there's no per-user identity table (D9), just a
    role. When auth is disabled (the default), every caller is treated as
    the coordinator, matching the rest of the API's open-by-default posture.
    """
    if not settings.auth_enabled:
        return COORDINATOR_IDENTITY

    if settings.coordinator_api_key and x_api_key == settings.coordinator_api_key:
        return COORDINATOR_IDENTITY
    if settings.automation_api_key and x_api_key == settings.automation_api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Automation identity cannot approve recommendations; a coordinator key is required.",
        )
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing or invalid API key.",
    )
