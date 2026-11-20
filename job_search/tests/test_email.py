"""The email artifact rendered as a mail-client-style card."""

from __future__ import annotations

from app.documents.email import format_email
from tests.conftest import login

TEXT = """\
Senior Machine Learning Engineer at Acme Speech.
We are looking for a senior engineer to own speech recognition quality across six languages.
You will build evaluation tooling, fine-tune Whisper models and work with product teams.
Must have Python, PyTorch and hands-on ASR experience. Remote within Europe.
"""


def test_one_run_on_body_gains_paragraphs_and_a_signature():
    view = format_email(
        "Dear Hiring Team, I am writing to apply for the role. My work cut word error rate "
        "from 23.4% to 11.8% on 1,240 hours of audio. I would welcome a conversation. "
        "Thank you for considering my application. Attachments: CV.pdf, CoverLetter.pdf",
        attachments=["CV.pdf", "CoverLetter.pdf"],
        company="OpenAI",
    )
    assert view.greeting == "Dear Hiring Team,"
    assert len(view.paragraphs) >= 2
    assert all("Attachments:" not in paragraph for paragraph in view.paragraphs)
    assert view.sign_off == "Best regards,"
    assert view.signature == "Lyle Okoth"
    assert view.to_label == "OpenAI hiring team"
    assert view.attachments == ["CV.pdf", "CoverLetter.pdf"]


def test_natural_paragraphs_and_a_name_are_kept():
    view = format_email(
        "Hello Acme Speech team,\n\nI have applied for the role. I spent four years on "
        "multilingual speech systems and built the evaluation harness.\n\nYour focus on "
        "recognition quality is the work I want next.\n\nThank you for your time.\n\nLyle Okoth",
        attachments=["CV", "Cover letter"],
        company="Acme Speech",
    )
    assert view.greeting == "Hello Acme Speech team,"
    assert view.signature == "Lyle Okoth"
    assert view.sign_off == "Best regards,"
    assert len(view.paragraphs) == 3
    assert view.paragraphs[-1] == "Thank you for your time."


def test_an_explicit_sign_off_is_separated():
    view = format_email(
        "Dear team,\n\nI would like to apply.\n\nKind regards,\nLyle Okoth",
        company="Acme",
    )
    assert view.greeting == "Dear team,"
    assert view.sign_off == "Kind regards,"
    assert view.signature == "Lyle Okoth"
    assert view.paragraphs == ["I would like to apply."]


def test_job_page_renders_the_email_card(client):
    login(client)
    response = client.post(
        "/api/jobs",
        json={"source_text": TEXT},
        headers={"X-CSRF-Token": client.get("/api/auth/me").json()["csrf_token"]},
    )
    assert response.status_code == 202, response.text
    job_id = response.json()["job_id"]

    page = client.get(f"/jobs/{job_id}").text
    assert 'class="email-card"' in page
    assert 'class="email-card__head"' in page
    assert ">From<" in page and ">To<" in page and ">Subject<" in page
    assert 'id="email-body"' in page
    assert 'class="email-card__greeting"' in page
    assert 'class="email-card__signoff"' in page
    assert 'class="email-card__signature"' in page
    assert 'class="email-attachment"' in page
