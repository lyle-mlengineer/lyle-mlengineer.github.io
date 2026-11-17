from datetime import timedelta
from io import BytesIO

from fastapi.testclient import TestClient

from app.models import Chunk, Document, Run
from app.models.base import utcnow
from app.pipeline.documents.chunking import MAX_TOKENS, chunk_pages
from app.pipeline.documents.expiry import expire_documents
from app.pipeline.documents.parsers import ParsedPage
from app.pipeline.documents.retrieval import search_chunks
from tests.conftest import TestingSession, auth_headers

PPTX_MIME = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


def _deck(slides: dict[int, str], total: int = 12) -> bytes:
    from pptx import Presentation
    from pptx.util import Inches

    presentation = Presentation()
    blank = presentation.slide_layouts[6]
    for index in range(1, total + 1):
        slide = presentation.slides.add_slide(blank)
        box = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(8), Inches(3))
        box.text_frame.text = slides.get(index, f"Talking point {index}")
    buffer = BytesIO()
    presentation.save(buffer)
    return buffer.getvalue()


def _pdf(pages: int, text: str = "") -> bytes:
    from pypdf import PdfWriter

    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=612, height=792)
    if text:
        writer.add_metadata({"/Title": text})
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def _run(client: TestClient, signup, serve_site) -> tuple[dict, dict]:
    pair = signup()
    response = client.post(
        "/v1/sites",
        json={"url": serve_site("no-images"), "title": "Sparse"},
        headers=auth_headers(pair),
    )
    assert response.status_code == 201, response.text
    site = response.json()
    response = client.post(
        f"/v1/sites/{site['id']}/analyze", headers=auth_headers(pair)
    )
    assert response.status_code == 200, response.text
    run = response.json()
    assert run["status"] == "succeeded", run.get("error")
    return pair, run


def _upload(
    client: TestClient,
    pair: dict,
    run_id: str,
    filename: str,
    data: bytes,
    mime: str,
    gap_key: str | None = None,
):
    form = {"gap_key": gap_key} if gap_key else None
    return client.post(
        f"/v1/runs/{run_id}/documents",
        files=[("files", (filename, data, mime))],
        data=form,
        headers=auth_headers(pair),
    )


def test_slide_seven_metric_cites_page_seven(client: TestClient, signup, serve_site) -> None:
    pair, run = _run(client, signup, serve_site)
    deck = _deck(
        {7: "2,100 monthly active creators as of October 2026."},
    )

    response = _upload(
        client,
        pair,
        run["id"],
        "growth-deck.pptx",
        deck,
        PPTX_MIME,
        gap_key="proof.metrics",
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["documents"][0]["pages"] == 12
    assert body["documents"][0]["chunks"] >= 12
    assert body["documents"][0]["extracted_facts"] >= 1

    facts = client.get(
        f"/v1/runs/{run['id']}/facts", headers=auth_headers(pair)
    ).json()
    fact = next(item for item in facts if item["key"] == "proof.metrics")
    assert fact["tier"] == "A"
    assert fact["source_type"] == "document"
    assert fact["source"] == "growth-deck.pptx"
    assert fact["source_page"] == 7
    assert "2,100 monthly active creators" in fact["source_quote"]
    assert fact["value"] == "2,100"
    assert fact["as_of"] == "2026-10"

    gaps = client.get(
        f"/v1/runs/{run['id']}/gaps", headers=auth_headers(pair)
    ).json()
    metric_gap = next(gap for gap in gaps["gaps"] if gap["key"] == "proof.metrics")
    assert metric_gap["status"] == "resolved"
    assert metric_gap["resolved_by"] == fact["id"]


def test_retrieval_never_crosses_tenants(client: TestClient, signup, serve_site) -> None:
    pair_a, run_a = _run(client, signup, serve_site)
    pair_b = signup(email="grace@example.com", tenant_name="Grace Labs")
    response = client.post(
        "/v1/sites",
        json={"url": serve_site("no-images"), "title": "Sparse"},
        headers=auth_headers(pair_b),
    )
    site_b = response.json()
    response = client.post(
        f"/v1/sites/{site_b['id']}/analyze", headers=auth_headers(pair_b)
    )
    run_b = response.json()

    response = _upload(
        client,
        pair_b,
        run_b["id"],
        "private-notes.txt",
        b"zebra-42 is the confidential creator count. zebra-42 stays private.",
        "text/plain",
    )
    assert response.status_code == 201, response.text
    document_b = response.json()["documents"][0]["document_id"]

    with TestingSession() as db:
        run_a_row = db.get(Run, run_a["id"])
        run_b_row = db.get(Run, run_b["id"])
        assert run_a_row is not None and run_b_row is not None
        assert search_chunks(db, run_a_row, "zebra-42 confidential creators") == []
        found = search_chunks(db, run_b_row, "zebra-42 confidential creators")
        assert found
        assert all(item.chunk.tenant_id == run_b_row.tenant_id for item in found)

    response = client.get(
        f"/v1/runs/{run_a['id']}/documents/{document_b}",
        headers=auth_headers(pair_a),
    )
    assert response.status_code == 404


def test_forty_one_page_pdf_is_rejected(client: TestClient, signup, serve_site) -> None:
    pair, run = _run(client, signup, serve_site)
    response = _upload(
        client, pair, run["id"], "long.pdf", _pdf(41), "application/pdf"
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "41" in detail
    assert "40" in detail

    documents = client.get(
        f"/v1/runs/{run['id']}/documents", headers=auth_headers(pair)
    ).json()
    assert documents[0]["status"] == "failed"


def test_malformed_pdf_fails_gracefully(client: TestClient, signup, serve_site) -> None:
    pair, run = _run(client, signup, serve_site)
    response = _upload(
        client,
        pair,
        run["id"],
        "broken.pdf",
        b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog >>\nendobj\n",
        "application/pdf",
        gap_key="proof.metrics",
    )
    assert response.status_code == 422
    assert "broken.pdf" in response.json()["detail"]

    gaps = client.get(
        f"/v1/runs/{run['id']}/gaps", headers=auth_headers(pair)
    ).json()
    metric_gap = next(gap for gap in gaps["gaps"] if gap["key"] == "proof.metrics")
    assert metric_gap["status"] == "open"


def test_mime_is_sniffed_and_size_limit_is_enforced(
    client: TestClient, signup, serve_site, monkeypatch
) -> None:
    pair, run = _run(client, signup, serve_site)

    response = _upload(
        client,
        pair,
        run["id"],
        "notes.pdf",
        b"this is plain text pretending to be a pdf",
        "application/pdf",
    )
    assert response.status_code == 422
    assert "does not match" in response.json()["detail"]

    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "max_document_bytes", 1024)
    response = _upload(
        client,
        pair,
        run["id"],
        "big.txt",
        b"x" * 4096,
        "text/plain",
    )
    assert response.status_code == 413
    assert "limit" in response.json()["detail"]


def test_file_count_limit(client: TestClient, signup, serve_site) -> None:
    pair, run = _run(client, signup, serve_site)
    response = client.post(
        f"/v1/runs/{run['id']}/documents",
        files=[
            ("files", (f"note-{index}.txt", b"hello world", "text/plain"))
            for index in range(6)
        ],
        headers=auth_headers(pair),
    )
    assert response.status_code == 422
    assert "at most 5 files" in response.json()["detail"]


def test_pin_and_expiry(client: TestClient, signup, serve_site) -> None:
    pair, run = _run(client, signup, serve_site)
    headers = auth_headers(pair)

    first = _upload(
        client, pair, run["id"], "brand-guide.txt", b"Brand voice is warm and direct.", "text/plain"
    )
    assert first.status_code == 201, first.text
    pinned_id = first.json()["documents"][0]["document_id"]

    response = client.post(
        f"/v1/runs/{run['id']}/documents/{pinned_id}/pin",
        json={"pinned": True},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["pinned_to_brand"] is True
    assert response.json()["expires_at"] is None

    second = _upload(
        client, pair, run["id"], "old-deck.txt", b"Old campaign notes.", "text/plain"
    )
    assert second.status_code == 201, second.text
    expiring_id = second.json()["documents"][0]["document_id"]

    with TestingSession() as db:
        report = expire_documents(db, now=utcnow() + timedelta(days=31))
        db.commit()
        assert report.expired == 1
        assert report.documents == [expiring_id]

    documents = client.get(f"/v1/runs/{run['id']}/documents", headers=headers).json()
    statuses = {item["id"]: item["status"] for item in documents}
    assert statuses[pinned_id] == "ready"
    assert statuses[expiring_id] == "expired"

    with TestingSession() as db:
        remaining = (
            db.query(Chunk).filter(Chunk.document_id == expiring_id).count()
        )
        assert remaining == 0
        expiring = db.get(Document, expiring_id)
        assert expiring is not None and expiring.chunk_count == 0


def test_chunking_keeps_pages_and_overlap() -> None:
    sentence = "the pipeline keeps each citation anchored to its own page"
    text = "\n".join(f"{sentence} item {index}" for index in range(220))
    drafts = chunk_pages([ParsedPage(number=4, kind="slide", text=text)])

    assert len(drafts) > 1
    assert all(draft.page == 4 for draft in drafts)
    assert all(draft.tokens <= MAX_TOKENS for draft in drafts)
    first_tail = drafts[0].text[-120:].split()[-6:]
    assert " ".join(first_tail) in drafts[1].text
