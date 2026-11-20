"""HTTP routes (spec Design > API). Every route except /health requires a valid Supabase access token."""

import hashlib
import logging
import time
import uuid
from collections import defaultdict, deque
from typing import Annotated
from uuid import UUID

import pypdfium2 as pdfium
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import Response

from rater.api.auth import AuthError, Principal
from rater.api.models import ClarifyBody, Created, RunDetail, RunList, RunSummary, SignedUrl
from rater.storage.objects import LocalObjectStore, SignatureError

log = logging.getLogger("rater.api")
router = APIRouter()

FINAL = {"resolved", "unsupported", "ambiguous"}


def _deps(request: Request):  # type: ignore[no-untyped-def]
    return request.app.state.deps


def require_user(request: Request) -> Principal:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sign in to continue.")
    try:
        return _deps(request).verifier.verify(token)  # type: ignore[no-any-return]
    except AuthError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Your session has expired. Sign in again.") from exc


User = Annotated[Principal, Depends(require_user)]


class RateLimiter:
    """Sliding one-minute window per user, held in memory per process (documented limitation)."""

    def __init__(self, per_minute: int, clock=time.monotonic) -> None:  # type: ignore[no-untyped-def]
        self._limit = per_minute
        self._clock = clock
        self._hits: dict[UUID, deque[float]] = defaultdict(deque)

    def allow(self, user: UUID) -> bool:
        now = self._clock()
        hits = self._hits[user]
        while hits and now - hits[0] > 60:
            hits.popleft()
        if len(hits) >= self._limit:
            return False
        hits.append(now)
        return True


def _validate_pdf(data: bytes, max_pages: int) -> int:
    if not data.startswith(b"%PDF-"):
        raise HTTPException(422, "Upload a PDF file. This file is not a PDF.")
    try:
        doc = pdfium.PdfDocument(data)
    except pdfium.PdfiumError as exc:
        if "password" in str(exc).lower():
            raise HTTPException(
                422, "This PDF is password-protected. Upload a copy without a password."
            ) from exc
        raise HTTPException(422, "This file isn't a readable PDF. Upload the original policy PDF.") from exc
    try:
        pages = len(doc)
    finally:
        doc.close()
    if pages == 0:
        raise HTTPException(422, "This PDF has no pages.")
    if pages > max_pages:
        raise HTTPException(
            422, f"This PDF has {pages} pages. Upload a policy of {max_pages} pages or fewer."
        )
    return pages


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/api/runs", status_code=202, response_model=Created, response_model_by_alias=True)
async def create_run(request: Request, user: User, file: Annotated[UploadFile, File()]) -> Created:
    deps = _deps(request)
    if not deps.limiter.allow(user.user_id):
        raise HTTPException(429, "Too many uploads. Wait a minute and try again.")
    data = await file.read(deps.max_bytes + 1)
    if len(data) > deps.max_bytes:
        raise HTTPException(
            413, f"This file is over {deps.max_bytes // (1024 * 1024)} MB. Upload a smaller PDF."
        )
    pages = _validate_pdf(data, deps.max_pages)
    sha = hashlib.sha256(data).hexdigest()
    key = f"{uuid.uuid4()}/{sha}.pdf"
    deps.objects.put(key, data)
    run = deps.store.create_run(user.user_id, file.filename or "policy.pdf", sha, key, pages)
    deps.queue.enqueue(run.id)
    deps.store.audit(str(user.user_id), "run.created", f"run:{run.id}")
    log.info("run %s: queued", run.id)
    return Created(id=run.id)


@router.get("/api/runs", response_model=RunList, response_model_by_alias=True)
def list_runs(request: Request, user: User, cursor: str | None = None) -> RunList:
    page = _deps(request).store.list_runs(user.user_id, cursor=cursor, limit=50)
    return RunList(items=[RunSummary.of(r) for r in page.items], next_cursor=page.next_cursor)


def _own_run(request: Request, user: Principal, run_id: UUID):  # type: ignore[no-untyped-def]
    run = _deps(request).store.get_run(user.user_id, run_id)
    if run is None:
        raise HTTPException(404, "Run not found.")
    return run


@router.get("/api/runs/{run_id}", response_model=RunDetail, response_model_by_alias=True)
def get_run(request: Request, user: User, run_id: UUID) -> RunDetail:
    return RunDetail.of(_own_run(request, user, run_id))


@router.get("/api/runs/{run_id}/pdf", response_model=SignedUrl, response_model_by_alias=True)
def pdf_url(request: Request, user: User, run_id: UUID) -> SignedUrl:
    run = _own_run(request, user, run_id)
    return SignedUrl(url=_deps(request).objects.signed_url(run.storage_key, ttl_s=300))


@router.get("/api/files/{key:path}")
def local_file(request: Request, user: User, key: str, exp: int = 0, sig: str = "") -> Response:
    objects = _deps(request).objects
    if not isinstance(objects, LocalObjectStore):
        raise HTTPException(404, "Not found.")
    try:
        objects.verify(key, exp, sig)
    except SignatureError as exc:
        raise HTTPException(403, "This link has expired. Open the PDF again from the run page.") from exc
    return Response(objects.get(key), media_type="application/pdf")


@router.post(
    "/api/runs/{run_id}/retry", status_code=202, response_model=Created, response_model_by_alias=True
)
def retry(request: Request, user: User, run_id: UUID) -> Created:
    deps = _deps(request)
    run = _own_run(request, user, run_id)
    if run.status != "failed":
        raise HTTPException(409, "Only a failed run can be retried.")
    deps.store.set_queued(run.id)
    deps.queue.enqueue(run.id)
    deps.store.audit(str(user.user_id), "run.retried", f"run:{run.id}")
    return Created(id=run.id)


@router.post(
    "/api/runs/{run_id}/clarify", status_code=202, response_model=Created, response_model_by_alias=True
)
def clarify(request: Request, user: User, run_id: UUID, body: ClarifyBody) -> Created:
    deps = _deps(request)
    run = _own_run(request, user, run_id)
    if run.status not in FINAL:
        raise HTTPException(409, "Wait for this run to finish before adding facts.")
    child = deps.store.create_run(
        user.user_id,
        run.file_name,
        run.pdf_sha256,
        run.storage_key,
        run.page_count,
        parent_run_id=run.id,
        overrides=body.facts,
    )
    deps.queue.enqueue(child.id)
    deps.store.audit(str(user.user_id), "run.clarified", f"run:{child.id}")
    return Created(id=child.id)
