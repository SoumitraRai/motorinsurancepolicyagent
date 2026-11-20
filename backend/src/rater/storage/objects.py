"""Object storage for uploaded PDFs: Supabase Storage in deployment, a local directory for development."""

import hashlib
import hmac
import time
from collections.abc import Callable
from pathlib import Path
from typing import Protocol
from urllib.parse import quote, urlencode

import httpx


class SignatureError(Exception):
    """A signed URL is expired or does not match its key."""


class ObjectStore(Protocol):
    def put(self, key: str, data: bytes) -> None: ...

    def get(self, key: str) -> bytes: ...

    def signed_url(self, key: str, ttl_s: int = 300) -> str: ...


class LocalObjectStore:
    """Files under `root`. Signed URLs point at the API's /api/files route and are HMAC-checked there."""

    def __init__(self, root: Path, secret: str, clock: Callable[[], float] = time.time) -> None:
        self._root = root.resolve()
        self._secret = secret.encode()
        self._clock = clock

    def _path(self, key: str) -> Path:
        path = (self._root / key).resolve()
        if not path.is_relative_to(self._root):
            raise ValueError(f"object key escapes the store: {key!r}")
        return path

    def put(self, key: str, data: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def _sign(self, key: str, exp: int) -> str:
        return hmac.new(self._secret, f"{key}\n{exp}".encode(), hashlib.sha256).hexdigest()

    def signed_url(self, key: str, ttl_s: int = 300) -> str:
        exp = int(self._clock()) + ttl_s
        return f"/api/files/{quote(key)}?" + urlencode({"exp": exp, "sig": self._sign(key, exp)})

    def verify(self, key: str, exp: int, sig: str) -> None:
        if self._clock() > exp or not hmac.compare_digest(self._sign(key, exp), sig):
            raise SignatureError(key)


class SupabaseObjectStore:
    """Supabase Storage REST API, authenticated with the service key (server-side only)."""

    def __init__(self, url: str, service_key: str, bucket: str, client: httpx.Client | None = None) -> None:
        self._base = url.rstrip("/") + "/storage/v1"
        self._bucket = bucket
        self._client = client or httpx.Client(timeout=60)
        self._auth = {"authorization": f"Bearer {service_key}", "apikey": service_key}

    def _object(self, key: str) -> str:
        return f"{self._base}/object/{self._bucket}/{quote(key)}"

    def put(self, key: str, data: bytes) -> None:
        r = self._client.post(
            self._object(key),
            content=data,
            headers={**self._auth, "content-type": "application/pdf", "x-upsert": "false"},
        )
        r.raise_for_status()

    def get(self, key: str) -> bytes:
        r = self._client.get(self._object(key), headers=self._auth)
        r.raise_for_status()
        return r.content

    def signed_url(self, key: str, ttl_s: int = 300) -> str:
        r = self._client.post(
            f"{self._base}/object/sign/{self._bucket}/{quote(key)}",
            json={"expiresIn": ttl_s},
            headers=self._auth,
        )
        r.raise_for_status()
        return self._base + r.json()["signedURL"]
