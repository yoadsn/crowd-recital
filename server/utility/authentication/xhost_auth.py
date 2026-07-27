from typing import Annotated, Optional

import jwt
from jwt import PyJWKClient
from dependency_injector.wiring import Provide, inject
from fastapi import Cookie, Depends
from pydantic import BaseModel

from containers import Container

# See https://docs.xhostd.com/oauth
XHOST_ISSUER = "https://auth.xhostd.com"
XHOST_JWKS_URL = "https://auth.xhostd.com/xhost-auth/jwks"
XHOST_ID_COOKIE_NAME = "__Host-xhost_id"

XhostIdCookie = Annotated[str | None, Cookie(alias=XHOST_ID_COOKIE_NAME, alias_priority=1)]

# Lazily built and cached - fetches/caches xhost's public keys.
_jwks_client: Optional[PyJWKClient] = None


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = PyJWKClient(XHOST_JWKS_URL)
    return _jwks_client


class XhostIdentification(BaseModel):
    sub: str
    email: str
    name: str


@inject
def get_xhost_identification(
    xhost_id_cookie: XhostIdCookie = None,
    auth_mode: str = Depends(Provide[Container.config.auth.mode]),
    xhost_audience: str = Depends(Provide[Container.config.auth.xhost_audience]),
) -> XhostIdentification | None:
    """Verifies the xhost identity cookie (if present) against xhost's published
    JWKS. Only active when AUTH_MODE=xhost and AUTH_XHOST_AUDIENCE is configured
    (must equal this channel's exact hostname).

    Never trust this cookie's contents without signature verification - that's
    handled here via PyJWKClient + jwt.decode (RS256 pinned, iss/aud/exp checked).
    """
    if auth_mode != "xhost" or not xhost_id_cookie or not xhost_audience:
        return None

    try:
        signing_key = _get_jwks_client().get_signing_key_from_jwt(xhost_id_cookie).key
        claims = jwt.decode(
            xhost_id_cookie,
            signing_key,
            algorithms=["RS256"],  # pin RS256 - never let the token pick its own alg
            issuer=XHOST_ISSUER,
            audience=xhost_audience,
        )
    except jwt.PyJWTError:
        return None

    return XhostIdentification(
        sub=claims["sub"],
        email=claims["email"],
        name=claims.get("name") or claims["email"],
    )
