import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from rater.storage.objects import LocalObjectStore, SignatureError, SupabaseObjectStore


def test_local_put_get_roundtrip(tmp_path: Path) -> None:
    store = LocalObjectStore(tmp_path, secret="s3cret")
    store.put("runs/a/x.pdf", b"%PDF-1.7 abc")
    assert LocalObjectStore(tmp_path, secret="s3cret").get("runs/a/x.pdf") == b"%PDF-1.7 abc"


def test_local_rejects_path_escape(tmp_path: Path) -> None:
    store = LocalObjectStore(tmp_path, secret="s")
    with pytest.raises(ValueError):
        store.put("../outside.pdf", b"x")


def test_signed_url_expires(tmp_path: Path) -> None:
    now = [1_000_000.0]
    store = LocalObjectStore(tmp_path, secret="s3cret", clock=lambda: now[0])
    store.put("k.pdf", b"x")
    url = store.signed_url("k.pdf", ttl_s=300)
    q = {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}
    assert store.verify("k.pdf", int(q["exp"]), q["sig"]) is None
    now[0] += 301
    with pytest.raises(SignatureError):
        store.verify("k.pdf", int(q["exp"]), q["sig"])


def test_signed_url_tamper_rejected(tmp_path: Path) -> None:
    store = LocalObjectStore(tmp_path, secret="s3cret", clock=lambda: 0.0)
    url = store.signed_url("k.pdf", ttl_s=300)
    q = {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}
    with pytest.raises(SignatureError):
        store.verify("other.pdf", int(q["exp"]), q["sig"])


def test_supabase_store_uses_storage_api() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.method == "POST" and "/object/sign/" in request.url.path:
            return httpx.Response(200, json={"signedURL": "/object/sign/policies/k.pdf?token=abc"})
        if request.method == "POST":
            return httpx.Response(200, json={"Key": "policies/k.pdf"})
        return httpx.Response(200, content=b"%PDF-bytes")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    store = SupabaseObjectStore("https://proj.supabase.co", "service-key", bucket="policies", client=client)
    store.put("k.pdf", b"%PDF-bytes")
    assert store.get("k.pdf") == b"%PDF-bytes"
    url = store.signed_url("k.pdf", ttl_s=300)

    assert url == "https://proj.supabase.co/storage/v1/object/sign/policies/k.pdf?token=abc"
    put, get, sign = seen
    assert put.url.path == "/storage/v1/object/policies/k.pdf"
    assert put.headers["authorization"] == "Bearer service-key"
    assert put.headers["content-type"] == "application/pdf"
    assert get.url.path == "/storage/v1/object/policies/k.pdf"
    assert json.loads(sign.content) == {"expiresIn": 300}


def test_supabase_store_raises_on_error() -> None:
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(500, text="nope")))
    store = SupabaseObjectStore("https://proj.supabase.co", "k", bucket="policies", client=client)
    with pytest.raises(httpx.HTTPStatusError):
        store.get("k.pdf")
