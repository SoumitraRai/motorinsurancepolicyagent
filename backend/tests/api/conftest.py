"""API test fixtures: a local RSA JWKS standing in for Supabase Auth, generated PDFs, and a wired app."""

import io
import json
import time
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import jwt
import pypdfium2 as pdfium
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from pypdf import PdfReader, PdfWriter

from rater.api.app import Deps, create_app
from rater.api.auth import JwtVerifier
from rater.storage.objects import LocalObjectStore
from rater.storage.postgres import PostgresStore
from rater.worker import PipelineOutput

USER = uuid.UUID("11111111-1111-1111-1111-111111111111")
OTHER = uuid.UUID("22222222-2222-2222-2222-222222222222")
ISSUER = "https://proj.supabase.co/auth/v1"


@pytest.fixture(scope="session")
def rsa_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(scope="session")
def jwks(rsa_key: rsa.RSAPrivateKey) -> dict[str, Any]:
    public = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(rsa_key.public_key()))
    public.update({"kid": "test-key", "alg": "RS256", "use": "sig"})
    return {"keys": [public]}


def make_token(key: rsa.RSAPrivateKey, user: uuid.UUID = USER, exp_in: int = 3600, **extra: Any) -> str:
    now = int(time.time())
    claims = {"sub": str(user), "aud": "authenticated", "iss": ISSUER, "iat": now, "exp": now + exp_in}
    claims.update(extra)
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": "test-key"})


def pdf_bytes(pages: int = 1) -> bytes:
    doc = pdfium.PdfDocument.new()
    for _ in range(pages):
        doc.new_page(595, 842)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def encrypted_pdf_bytes() -> bytes:
    writer = PdfWriter()
    for page in PdfReader(io.BytesIO(pdf_bytes(1))).pages:
        writer.add_page(page)
    writer.encrypt(user_password="secret", owner_password="owner")
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


class FakePipeline:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, str] | None]] = []

    def __call__(self, pdf: bytes, file_name: str, overrides: dict[str, str] | None = None) -> PipelineOutput:
        self.calls.append((file_name, overrides))
        result = {"status": "unsupported", "facts": {}, "rates": {}, "trace": [], "confidence": {}}
        return PipelineOutput("unsupported", json.dumps(result), versions={"test": "1"}, switches={})


@pytest.fixture
def wired(
    clean_db: str, tmp_path: Path, jwks: dict[str, Any]
) -> Iterator[tuple[TestClient, PostgresStore, LocalObjectStore, FakePipeline]]:
    store = PostgresStore(clean_db)
    objects = LocalObjectStore(tmp_path / "objects", secret="file-secret")
    verifier = JwtVerifier(keys=lambda: jwks, issuer=ISSUER)
    pipeline = FakePipeline()
    app = create_app(Deps(store=store, queue=store, objects=objects, verifier=verifier, static_dir=None))
    with TestClient(app) as client:
        yield client, store, objects, pipeline
    store.close()
