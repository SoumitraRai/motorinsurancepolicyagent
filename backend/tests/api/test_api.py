import json
import logging
import uuid

import pytest
from fastapi.routing import APIRoute

from rater.api.app import MAX_PAGES
from rater.api.routes import router
from rater.worker import NotReadyPipeline, process_one
from tests.api.conftest import OTHER, encrypted_pdf_bytes, make_token, pdf_bytes


def auth(rsa_key, user=None):  # type: ignore[no-untyped-def]
    token = make_token(rsa_key) if user is None else make_token(rsa_key, user=user)
    return {"Authorization": f"Bearer {token}"}


def upload(client, headers, data: bytes, name: str = "policy.pdf"):  # type: ignore[no-untyped-def]
    return client.post("/api/runs", headers=headers, files={"file": (name, data, "application/pdf")})


def test_health_is_open(wired) -> None:  # type: ignore[no-untyped-def]
    client, *_ = wired
    assert client.get("/health").status_code == 200


def test_all_routes_require_jwt_except_health(wired) -> None:  # type: ignore[no-untyped-def]
    client, *_ = wired
    # FastAPI 0.165 nests included routers, so enumerate the router the app includes.
    routes = [r for r in router.routes if isinstance(r, APIRoute) and r.path != "/health"]
    assert len(routes) >= 6
    for route in routes:
        path = route.path.replace("{run_id}", str(uuid.uuid4())).replace("{key:path}", "k.pdf")
        for method in route.methods:
            resp = client.request(method, path)
            assert resp.status_code == 401, (method, path, resp.status_code)


def test_expired_or_wrong_audience_token_rejected(wired, rsa_key) -> None:  # type: ignore[no-untyped-def]
    client, *_ = wired
    expired = make_token(rsa_key, exp_in=-10)
    wrong_aud = make_token(rsa_key, aud="anon")
    for token in (expired, wrong_aud, "not-a-jwt"):
        assert client.get("/api/runs", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_upload_limits(wired, rsa_key) -> None:  # type: ignore[no-untyped-def]
    client, *_ = wired
    h = auth(rsa_key)
    too_big = b"%PDF-1.7\n" + b"0" * (25 * 1024 * 1024 + 1)
    r = upload(client, h, too_big)
    assert r.status_code == 413 and "25 MB" in r.json()["detail"]
    r = upload(client, h, pdf_bytes(MAX_PAGES + 1))
    assert r.status_code == 422 and f"{MAX_PAGES} pages" in r.json()["detail"]
    r = upload(client, h, b"hello, not a pdf", name="notes.txt")
    assert r.status_code == 422 and "PDF" in r.json()["detail"]


def test_upload_rejects_encrypted_and_corrupt(wired, rsa_key) -> None:  # type: ignore[no-untyped-def]
    client, *_ = wired
    h = auth(rsa_key)
    r = upload(client, h, encrypted_pdf_bytes())
    assert r.status_code == 422 and "password" in r.json()["detail"].lower()
    r = upload(client, h, b"%PDF-1.7\n garbage that is not a pdf body")
    assert r.status_code == 422 and "readable PDF" in r.json()["detail"]


def test_upload_then_worker_completes(wired, rsa_key) -> None:  # type: ignore[no-untyped-def]
    client, store, objects, pipeline = wired
    h = auth(rsa_key)
    r = upload(client, h, pdf_bytes(2))
    assert r.status_code == 202
    run_id = r.json()["id"]
    assert client.get(f"/api/runs/{run_id}", headers=h).json()["status"] == "queued"

    assert process_one(store, store, objects, pipeline) is True
    detail = client.get(f"/api/runs/{run_id}", headers=h).json()
    assert detail["status"] == "unsupported"
    assert detail["result"]["status"] == "unsupported"
    assert detail["pageCount"] == 2
    assert pipeline.calls == [("policy.pdf", None)]
    listed = client.get("/api/runs", headers=h).json()
    assert [row["id"] for row in listed["items"]] == [run_id]


def test_other_user_gets_404(wired, rsa_key) -> None:  # type: ignore[no-untyped-def]
    client, *_ = wired
    run_id = upload(client, auth(rsa_key), pdf_bytes(1)).json()["id"]
    assert client.get(f"/api/runs/{run_id}", headers=auth(rsa_key, OTHER)).status_code == 404
    assert client.get(f"/api/runs/{run_id}/pdf", headers=auth(rsa_key, OTHER)).status_code == 404


def test_pdf_signed_url_serves_original_bytes(wired, rsa_key) -> None:  # type: ignore[no-untyped-def]
    client, *_ = wired
    h = auth(rsa_key)
    data = pdf_bytes(1)
    run_id = upload(client, h, data).json()["id"]
    url = client.get(f"/api/runs/{run_id}/pdf", headers=h).json()["url"]
    got = client.get(url, headers=h)
    assert got.status_code == 200 and got.content == data
    tampered = url.replace("sig=", "sig=0")
    assert client.get(tampered, headers=h).status_code == 403


def test_worker_failure_marks_run_failed_and_retry_requeues(wired, rsa_key) -> None:  # type: ignore[no-untyped-def]
    client, store, objects, _ = wired
    h = auth(rsa_key)
    run_id = upload(client, h, pdf_bytes(1)).json()["id"]

    def broken(pdf: bytes, file_name: str, overrides=None):  # type: ignore[no-untyped-def]
        raise RuntimeError("engine exploded")

    assert process_one(store, store, objects, broken) is True
    detail = client.get(f"/api/runs/{run_id}", headers=h).json()
    assert detail["status"] == "failed" and detail["error"] == "Analysis failed. Retry this run."
    assert client.post(f"/api/runs/{run_id}/retry", headers=h).status_code == 202
    assert client.get(f"/api/runs/{run_id}", headers=h).json()["status"] == "queued"


def test_retry_only_for_failed_runs(wired, rsa_key) -> None:  # type: ignore[no-untyped-def]
    client, *_ = wired
    h = auth(rsa_key)
    run_id = upload(client, h, pdf_bytes(1)).json()["id"]
    assert client.post(f"/api/runs/{run_id}/retry", headers=h).status_code == 409


def test_clarify_creates_linked_run_with_overrides(wired, rsa_key) -> None:  # type: ignore[no-untyped-def]
    client, store, objects, pipeline = wired
    h = auth(rsa_key)
    run_id = upload(client, h, pdf_bytes(1)).json()["id"]
    process_one(store, store, objects, pipeline)
    r = client.post(f"/api/runs/{run_id}/clarify", headers=h, json={"facts": {"manufactureYear": "2019"}})
    assert r.status_code == 202
    child = client.get(f"/api/runs/{r.json()['id']}", headers=h).json()
    assert child["parentRunId"] == run_id
    process_one(store, store, objects, pipeline)
    assert pipeline.calls[-1] == ("policy.pdf", {"manufactureYear": "2019"})


def test_clarify_rejects_unknown_fields(wired, rsa_key) -> None:  # type: ignore[no-untyped-def]
    client, *_ = wired
    h = auth(rsa_key)
    run_id = upload(client, h, pdf_bytes(1)).json()["id"]
    r = client.post(f"/api/runs/{run_id}/clarify", headers=h, json={"facts": {}, "extra": 1})
    assert r.status_code == 422


def test_upload_rate_limited(wired, rsa_key) -> None:  # type: ignore[no-untyped-def]
    client, *_ = wired
    h = auth(rsa_key)
    codes = [upload(client, h, pdf_bytes(1)).status_code for _ in range(11)]
    assert codes[:10] == [202] * 10 and codes[10] == 429


def test_audit_events_for_state_changes(wired, rsa_key, clean_db) -> None:  # type: ignore[no-untyped-def]
    import psycopg

    client, *_ = wired
    upload(client, auth(rsa_key), pdf_bytes(1))
    with psycopg.connect(clean_db) as conn:
        actions = [r[0] for r in conn.execute("select action from audit_events").fetchall()]
    assert actions == ["run.created"]


def test_logs_contain_no_fact_values(wired, rsa_key, caplog: pytest.LogCaptureFixture) -> None:  # type: ignore[no-untyped-def]
    client, store, objects, _ = wired
    secret_value = "HR-26-FB-8239 MAHINDRA"

    def leaky(pdf: bytes, file_name: str, overrides=None):  # type: ignore[no-untyped-def]
        raise ValueError(f"could not parse {secret_value}")

    caplog.set_level(logging.DEBUG)
    upload(client, auth(rsa_key), pdf_bytes(1), name="secret-name.pdf")
    process_one(store, store, objects, leaky)
    text = "\n".join(r.getMessage() for r in caplog.records)
    assert secret_value not in text
    assert "secret-name.pdf" not in text


def test_not_ready_pipeline_is_honest() -> None:
    out = NotReadyPipeline()(b"%PDF", "x.pdf")
    body = json.loads(out.result_json)
    assert out.status == body["status"] == "unsupported"
    assert "analysis engine not deployed" in body["confidence"]["reason"]
    assert body["rates"]["od"]["ratePercent"] is None and body["rates"]["tp"]["ratePercent"] is None
