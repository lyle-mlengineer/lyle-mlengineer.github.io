"""Resume and retry: continuing a stopped run from its first unfinished step."""

from __future__ import annotations

from sqlalchemy import select

from app.db import get_session_factory
from app.jobs.pipeline import PIPELINE_ORDER, _prior_outputs, run_remaining_skills
from app.models import Artifact, Job, Run
from app.providers.llm.base import LLMProviderError
from app.providers.llm.fake import FakeLLMProvider
from app.skills.registry import FAKE_RESPONSES
from tests.conftest import login

TEXT = """\
Senior Machine Learning Engineer at Acme Speech.
We are looking for a senior engineer to own speech recognition quality across six languages.
You will build evaluation tooling, fine-tune Whisper models and work with product teams.
Must have Python, PyTorch and hands-on ASR experience. Remote within Europe.
"""


def _authed(client):
    login(client)
    return client


def headers(client) -> dict[str, str]:
    return {"X-CSRF-Token": client.get("/api/auth/me").json()["csrf_token"]}


class FlakyLLM(FakeLLMProvider):
    """Fails the nth call the way a provider error would, then behaves normally."""

    def __init__(self, responses: dict[str, str], fail_at: int) -> None:
        super().__init__(responses)
        self.count = 0
        self.fail_at = fail_at

    def complete(self, messages, **kwargs):
        self.count += 1
        if self.count == self.fail_at:
            raise LLMProviderError("The provider returned 429 and retries were exhausted.")
        return super().complete(messages, **kwargs)


def _add(client) -> dict:
    response = client.post("/api/jobs", json={"source_text": TEXT}, headers=headers(client))
    assert response.status_code == 202, response.text
    return response.json()


def _fail_run_at(client, at: int) -> int:
    """Create a job whose first run fails at call number ``at``, return the job id."""
    client.app.state.llm = FlakyLLM(FAKE_RESPONSES, fail_at=at)
    return _add(client)["job_id"]


def test_resume_continues_from_the_failed_step_and_reuses_prior_outputs(client, settings):
    authed = _authed(client)
    # Call 1 extraction, 2 summary, 3 research, 4 = cv_writing (mandatory) fails.
    job_id = _fail_run_at(authed, 4)

    factory = get_session_factory(settings)
    with factory() as db:
        run = db.scalar(select(Run).where(Run.job_id == job_id).order_by(Run.id.desc()).limit(1))
        assert run.status == "failed"
        assert _prior_outputs(db, job_id, exclude_run=-1)  # completed steps survive the failure
        assert "job_extraction" in _prior_outputs(db, job_id, exclude_run=-1)
        assert run_remaining_skills(db, run) == tuple(PIPELINE_ORDER[3:])

    page = authed.get(f"/jobs/{job_id}").text
    assert "Resume run" in page
    assert 'id="run-resume"' in page
    assert "Start over" in page
    assert "steps__retry" in page

    authed.app.state.llm = FakeLLMProvider(FAKE_RESPONSES)
    resumed = authed.post(f"/api/jobs/{job_id}/resume", headers=headers(authed))
    assert resumed.status_code == 202, resumed.text
    body = resumed.json()
    assert body["skills"] == list(PIPELINE_ORDER[3:])
    assert body["resumed_from"] == run.id

    done = authed.get(body["poll_url"]).json()
    assert done["status"] == "succeeded"
    assert done["total_steps"] == len(PIPELINE_ORDER) - 3

    with factory() as db:
        # The completed steps were not re-run: research exists exactly once,
        # and the resume run never mentioned extraction or summary.
        kinds = db.scalars(select(Artifact.kind)).all()
        assert kinds.count("company_research") == 1
        resume_run = db.get(Run, body["run_id"])
        assert all(step.skill not in {"job_extraction", "job_summary"} for step in resume_run.steps)
        assert resume_run.status == "succeeded"

    page = authed.get(f"/jobs/{job_id}").text
    assert "Run again" in page
    assert "Resume run" not in page


def test_resume_is_rejected_while_a_run_is_in_flight(client, monkeypatch):
    import app.routes.jobs as jobs_routes

    monkeypatch.setattr(jobs_routes, "execute_run", lambda *args, **kwargs: None)
    authed = _authed(client)
    created = _add(authed)
    response = authed.post(f"/api/jobs/{created['job_id']}/resume", headers=headers(authed))
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


def test_resume_is_rejected_when_the_last_run_succeeded(client):
    authed = _authed(client)
    created = _add(authed)
    response = authed.post(f"/api/jobs/{created['job_id']}/resume", headers=headers(authed))
    assert response.status_code == 409
    assert "already finished" in response.json()["error"]["message"]


def test_resume_requires_login_and_csrf(client):
    authed = _authed(client)
    job_id = _add(authed)["job_id"]

    client.cookies.clear()
    assert client.post(f"/api/jobs/{job_id}/resume").status_code == 401

    login(client)
    assert client.post(f"/api/jobs/{job_id}/resume").status_code == 403


def test_resume_404s_for_an_unknown_job(client):
    authed = _authed(client)
    assert authed.post("/api/jobs/999999/resume", headers=headers(authed)).status_code == 404

def test_jobs_list_offers_resume_only_while_steps_remain(client):
    authed = _authed(client)
    job_id = _fail_run_at(authed, 4)

    html = authed.get("/jobs").text
    assert f'data-resume-job="{job_id}"' in html
    assert "steps left" in html
    assert "/static/js/jobs.js" in html
    assert 'class="list__link"' in html

    authed.app.state.llm = FakeLLMProvider(FAKE_RESPONSES)
    resumed = authed.post(f"/api/jobs/{job_id}/resume", headers=headers(authed))
    assert resumed.status_code == 202
    assert authed.get(resumed.json()["poll_url"]).json()["status"] == "succeeded"

    html = authed.get("/jobs").text
    assert f'data-resume-job="{job_id}"' not in html


def test_dashboard_lists_a_stopped_run_with_resume(client):
    authed = _authed(client)
    job_id = _fail_run_at(authed, 4)

    html = authed.get("/dashboard").text
    assert "Needs action" in html
    assert f'data-resume-job="{job_id}"' in html
    assert "Run stopped" in html
    assert "step" in html and "left" in html
    assert "/static/js/jobs.js" in html

    authed.app.state.llm = FakeLLMProvider(FAKE_RESPONSES)
    resumed = authed.post(f"/api/jobs/{job_id}/resume", headers=headers(authed))
    assert resumed.status_code == 202
    assert authed.get(resumed.json()["poll_url"]).json()["status"] == "succeeded"

    html = authed.get("/dashboard").text
    assert f'data-resume-job="{job_id}"' not in html


def test_company_page_offers_resume_for_a_stopped_job(client, settings):
    authed = _authed(client)
    job_id = _fail_run_at(authed, 4)

    with get_session_factory(settings)() as db:
        company_id = db.get(Job, job_id).company_id

    html = authed.get(f"/companies/{company_id}").text
    assert f'data-resume-job="{job_id}"' in html
    assert "steps left" in html
    assert "/static/js/jobs.js" in html

    authed.app.state.llm = FakeLLMProvider(FAKE_RESPONSES)
    resumed = authed.post(f"/api/jobs/{job_id}/resume", headers=headers(authed))
    assert resumed.status_code == 202
    assert authed.get(resumed.json()["poll_url"]).json()["status"] == "succeeded"

    html = authed.get(f"/companies/{company_id}").text
    assert f'data-resume-job="{job_id}"' not in html


def test_resume_partial_is_shared_and_pluralises_steps(client):
    env = client.app.state.templates.env
    template = env.from_string(
        '{% from "partials/resume_chip.html" import resume_chip, steps_left %}'
        "{{ steps_left(1) }}|{{ steps_left(3) }}|{{ resume_chip(7) }}"
    )
    html = template.render()

    assert "1 step left" in html
    assert "3 steps left" in html
    assert 'data-resume-job="7"' in html

    button = env.from_string(
        '{% from "partials/resume_chip.html" import resume_chip %}{{ resume_chip(7, "button") }}'
    ).render()
    assert 'id="run-resume"' in button
    assert "Resume run" in button
    assert "data-resume-job" not in button
