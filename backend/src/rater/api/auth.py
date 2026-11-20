"""Server-side verification of Supabase Auth access tokens (JWT, asymmetric keys from the project JWKS)."""

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import httpx
import jwt


class AuthError(Exception):
    """The token is missing, malformed, expired, or not signed by a known key."""


@dataclass(frozen=True)
class Principal:
    user_id: UUID
    email: str | None


def jwks_fetcher(
    url: str, ttl_s: int = 600, client: httpx.Client | None = None
) -> Callable[[], dict[str, Any]]:
    """Fetch and cache the JWKS document; refetch after `ttl_s`."""
    http = client or httpx.Client(timeout=10)
    cache: dict[str, Any] = {"at": 0.0, "doc": None}

    def keys() -> dict[str, Any]:
        if cache["doc"] is None or time.monotonic() - cache["at"] > ttl_s:
            r = http.get(url)
            r.raise_for_status()
            cache.update(at=time.monotonic(), doc=r.json())
        return cache["doc"]  # type: ignore[no-any-return]

    return keys


class JwtVerifier:
    def __init__(
        self, keys: Callable[[], dict[str, Any]], issuer: str | None, audience: str = "authenticated"
    ) -> None:
        self._keys = keys
        self._issuer = issuer
        self._audience = audience

    def verify(self, token: str) -> Principal:
        try:
            kid = jwt.get_unverified_header(token).get("kid")
            jwk_set = jwt.PyJWKSet.from_dict(self._keys())
            key = next((k for k in jwk_set.keys if k.key_id == kid), None)
            if key is None:
                raise AuthError("unknown signing key")
            claims = jwt.decode(
                token,
                key.key,
                algorithms=["RS256", "ES256"],
                audience=self._audience,
                issuer=self._issuer,
                options={"require": ["exp", "sub", "aud"]},
            )
            return Principal(user_id=UUID(claims["sub"]), email=claims.get("email"))
        except AuthError:
            raise
        except (jwt.PyJWTError, ValueError, KeyError) as exc:
            raise AuthError(type(exc).__name__) from exc
