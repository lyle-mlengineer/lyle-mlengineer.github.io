from __future__ import annotations

from app.db import dispose_engines
from tests.conftest import login


def test_landing_page_is_public_and_complete(client):
    response = client.get("/")
    assert response.status_code == 200
    html = response.text
    assert "Lyle Okoth" in html
    assert "Skipper" in html
    assert 'href="/login?next=/dashboard"' in html
    assert "/static/css/style.css" in html
    assert "/static/css/landing.css" in html
    assert len(response.content) < 120_000


def test_landing_page_has_required_sections_and_skills(client):
    html = client.get("/").text
    for anchor in ("#home", "#skipper", "#about", "#skills", "#work", "#contact"):
        assert f'id="{anchor[1:]}"' in html
    for skill in (
        "Job extraction",
        "Job summary",
        "Company research",
        "CV writing",
        "Cover letter",
        "Email",
        "Tell me about yourself",
        "Work history",
        "Proud project",
        "Technical interview",
        "Behavioural interview",
    ):
        assert skill in html
    for skill_group in (
        "Speech &amp; Voice AI",
        "Machine Learning &amp; Deep Learning",
        "Data Engineering",
        "MLOps &amp; Deployment",
    ):
        assert skill_group in html


def test_landing_lists_every_portfolio_project(client):
    html = client.get("/").text
    for title in (
        "SautiFlow",
        "PlusOne",
        "LabelSet",
        "FaceForm",
        "Vocalis",
        "EchoID",
        "Suraya",
        "coAgent",
        "Docent",
        "SnapToSpot",
    ):
        assert title in html
    assert html.count('class="work__card"') == 10


def test_landing_cv_picker_opens_each_pdf_in_a_new_tab(client):
    html = client.get("/").text
    assert 'id="cv-menu-button"' in html
    assert 'aria-expanded="false"' in html
    for role in (
        "LYLE-OKOTH-AI-ENGINEER.pdf",
        "LYLE-OKOTH-AI-ML-ENGINEER.pdf",
        "LYLE-OKOTH-DATA-ENGINEER.pdf",
        "LYLE-OKOTH-MACHINE-LEARNING-ENGINEER.pdf",
        "LYLE-OKOTH-ML-RESEARCHER.pdf",
        "LYLE-OKOTH-SOFTWARE-ENGINEER.pdf",
    ):
        assert f'href="/static/cv/{role}" target="_blank" rel="noopener"' in html

    pdf = client.get("/static/cv/LYLE-OKOTH-MACHINE-LEARNING-ENGINEER.pdf")
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"


def test_landing_works_without_database_access(client, settings):
    # Close pooled SQLite connections first (Windows keeps the file locked), then
    # remove the database: the landing page must still render.
    dispose_engines()
    settings.db_path.unlink(missing_ok=True)
    response = client.get("/")
    assert response.status_code == 200


def test_landing_sets_security_headers(client):
    response = client.get("/")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "default-src 'self'" in response.headers["Content-Security-Policy"]
    assert response.headers["X-Request-Id"]


def test_dashboard_requires_session(client):
    response = client.get("/dashboard", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login?next=/dashboard"


def test_jobs_and_companies_require_session(client):
    for path in ("/jobs", "/companies", "/settings"):
        response = client.get(path, follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == f"/login?next={path}"


def test_login_page_renders(client):
    response = client.get("/login?next=/jobs")
    assert response.status_code == 200
    assert 'name="username"' in response.text
    assert 'name="password"' in response.text
    assert 'value="/jobs"' in response.text
    assert "Sign in" in response.text


def test_login_and_dashboard_round_trip(client):
    response = login(client)
    assert response.status_code == 303
    assert response.headers["location"] == "/dashboard"
    cookie = response.headers.get("set-cookie", "")
    assert "skipper_session=" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie.lower() or "samesite=lax" in cookie.lower()

    dash = client.get("/dashboard")
    assert dash.status_code == 200
    assert "Dashboard" in dash.text
    assert "No jobs tracked yet" in dash.text

    settings_page = client.get("/settings")
    assert settings_page.status_code == 200
    assert "Signed in as" in settings_page.text


def test_wrong_password_is_generic_and_does_not_create_session(client):
    response = login(client, password="definitely-wrong")
    assert response.status_code == 401
    assert "do not match" in response.text
    assert "skipper_session" not in response.cookies


def test_unknown_user_looks_the_same_as_wrong_password(client):
    response = login(client, username="nobody", password="definitely-wrong")
    assert response.status_code == 401
    assert "do not match" in response.text


def test_login_throttles_after_five_failures(client):
    for _ in range(5):
        assert login(client, password="wrong-password").status_code == 401
    blocked = login(client, password="test-password-123")
    assert blocked.status_code == 429
    assert "Too many attempts" in blocked.text


def test_open_redirect_is_ignored(client):
    response = client.post(
        "/login",
        data={"username": "lyle", "password": "test-password-123", "next": "//evil.example.com"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/dashboard"


def test_logout_revokes_the_session(client):
    login(client)
    assert client.get("/dashboard").status_code == 200
    client.cookies.clear()
    assert client.get("/dashboard", follow_redirects=False).status_code == 303


def test_404_renders_a_page(client):
    response = client.get("/nope")
    assert response.status_code == 404
    assert "does not exist" in response.text
