from __future__ import annotations

from io import BytesIO

from docx import Document
from sqlalchemy import select

from app.db import get_session_factory
from app.documents.letters import build_letter_docx, render_letter_pdf
from app.documents.resume import letter_filename
from app.models import Artifact, Job
from app.providers.llm.base import ChatMessage, LLMProvider, LLMResponse
from app.providers.llm.fake import FakeLLMProvider
from app.skills.fixtures import FAKE_COVER
from app.skills.registry import FAKE_RESPONSES
from tests.conftest import login

TEXT = """\
Senior Machine Learning Engineer at Acme Speech.
We are looking for a senior engineer to own speech recognition quality across six languages.
You will build evaluation tooling, fine-tune Whisper models and work with product teams.
Must have Python, PyTorch and hands-on ASR experience. Remote within Europe.
"""


def headers(client) -> dict[str, str]:
    return {"X-CSRF-Token": client.get("/api/auth/me").json()["csrf_token"]}


def _run(client):
    login(client)
    response = client.post("/api/jobs", json={"source_text": TEXT}, headers=headers(client))
    assert response.status_code == 202, response.text
    return response.json()["job_id"]


def test_cover_letter_is_one_page_and_names_the_company():
    content = build_letter_docx(FAKE_COVER, headline="Senior ML Engineer | Acme Speech")
    text = "\n".join(paragraph.text for paragraph in Document(BytesIO(content)).paragraphs)
    assert "LYLE OKOTH" in text
    assert "SENIOR ML ENGINEER | ACME SPEECH" in text
    assert "linkedin.com/in/lyle-okoth" in text
    assert "Dear Acme Speech team," in text
    assert "Sincerely," in text
    result = render_letter_pdf(
        content,
        FAKE_COVER,
        soffice_path="definitely-not-installed",
        headline="Senior ML Engineer | Acme Speech",
    )
    assert result.engine == "reportlab"
    assert result.pages == 1
    assert result.content.startswith(b"%PDF-")


def test_letter_filename_is_ats_safe():
    assert letter_filename("Acme Speech, GmbH", "Senior ML Engineer", 2, "pdf") == (
        "LYLE-OKOTH-ACME-SPEECH-GMBH-SENIOR-ML-ENGINEER-COVER-LETTER-v2.pdf"
    )


def test_full_pack_creates_cover_email_and_interview_artifacts(client, settings):
    job_id = _run(client)
    factory = get_session_factory(settings)
    with factory() as db:
        job = db.get(Job, job_id)
        current = {
            artifact.kind: artifact
            for artifact in db.scalars(
                select(Artifact).where(Artifact.job_id == job.id, Artifact.is_current.is_(True))
            ).all()
        }
        assert job.status == "ready"
        assert {
            "cover_letter_pdf",
            "cover_letter_docx",
            "email",
            "company_research",
            "tell_me_about_yourself",
            "work_history",
            "proud_project",
            "technical_interview",
            "system_design",
            "low_level_design",
            "coding",
            "behavioral_interview",
        } <= set(current)
        assert current["cover_letter_pdf"].version == current["cover_letter_docx"].version == 1
        assert current["email"].meta_json["payload"]["subject"]
        assert "Acme Speech" in current["cover_letter_pdf"].meta_json["letter"]["greeting"]
        assert current["technical_interview"].meta_json["payload"]["questions"]
        assert current["system_design"].meta_json["payload"]["questions"]
        assert current["low_level_design"].meta_json["payload"]["questions"]
        assert current["coding"].meta_json["payload"]["problems"]
        cover_id = current["cover_letter_pdf"].id
        email_id = current["email"].id

    page = client.get(f"/jobs/{job_id}")
    assert page.status_code == 200
    assert "Cover letter" in page.text
    assert "Application email" in page.text
    assert f"/api/artifacts/{cover_id}/preview" in page.text
    assert "Copy body" in page.text
    assert "Interview pack" in page.text
    assert "System design" in page.text
    assert "Low-level design" in page.text
    assert "Coding interview" in page.text
    assert "Requirements" in page.text
    assert "Core entities" in page.text
    assert "Data flow" in page.text
    assert "Deep dives" in page.text
    assert "Class design" in page.text
    assert "Implementation" in page.text
    assert "Extensibility" in page.text
    assert "Questions the interviewer may ask" in page.text
    assert "Questions to ask the interviewer" in page.text
    assert "Obvious solution" in page.text
    assert "Optimised solution" in page.text
    assert "Runtime:" in page.text
    assert "Storage:" in page.text
    assert "Diagram" in page.text
    assert 'data-interview-kind="system_design"' in page.text
    assert "/static/js/system_design.js" in page.text
    assert page.text.count('class="design-section design-section--') >= 6
    assert '<span class="design-section__label">Requirements</span>' in page.text
    assert 'class="prose-code"' in page.text

    assert client.get(f"/api/artifacts/{cover_id}/download").status_code == 200
    assert client.get(f"/api/artifacts/{email_id}/download").status_code == 200


def test_failed_optional_step_does_not_fail_the_run(client, settings):
    login(client)
    client.app.state.llm = FakeLLMProvider({**FAKE_RESPONSES, "email_writing": "{}"})
    response = client.post("/api/jobs", json={"source_text": TEXT}, headers=headers(client))
    assert response.status_code == 202
    run = client.get(response.json()["poll_url"]).json()
    assert run["status"] == "succeeded"
    assert next(step for step in run["steps"] if step["skill"] == "email_writing")["status"] == "failed"
    with get_session_factory(settings)() as db:
        assert db.get(Job, response.json()["job_id"]).status == "reviewing"


def test_cover_letter_regenerates_independently(client, settings):
    job_id = _run(client)
    response = client.post(
        f"/api/jobs/{job_id}/regenerate", json={"skill": "cover_letter"}, headers=headers(client)
    )
    assert response.status_code == 202, response.text
    run = client.get(response.json()["poll_url"]).json()
    assert run["status"] == "succeeded"
    assert [step["skill"] for step in run["steps"]] == ["cover_letter"]
    with get_session_factory(settings)() as db:
        rows = db.scalars(
            select(Artifact)
            .where(Artifact.job_id == job_id, Artifact.kind == "cover_letter_pdf")
            .order_by(Artifact.version)
        ).all()
        assert [row.version for row in rows] == [1, 2]
        assert rows[0].is_current is False and rows[1].is_current is True


def test_overlong_cover_letter_closing_is_clipped_not_failed(client, settings):
    """Regression: the model's closing can exceed the schema cap by a sentence."""
    import json

    login(client)
    long_closing = (
        "I would welcome the chance to talk through how my evaluation and speech work could help "
        "your team ship better models across every language and every release, and I am happy to "
        "walk through the trade-offs in detail."
    )
    assert len(long_closing) > 120
    client.app.state.llm = FakeLLMProvider(
        {**FAKE_RESPONSES, "cover_letter": json.dumps({**FAKE_COVER, "closing": long_closing})}
    )

    response = client.post("/api/jobs", json={"source_text": TEXT}, headers=headers(client))
    assert response.status_code == 202, response.text
    run = client.get(response.json()["poll_url"]).json()
    assert run["status"] == "succeeded"
    cover = next(step for step in run["steps"] if step["skill"] == "cover_letter")
    assert cover["status"] == "succeeded"

    with get_session_factory(settings)() as db:
        artifact = db.scalar(
            select(Artifact).where(
                Artifact.job_id == response.json()["job_id"],
                Artifact.kind == "cover_letter_pdf",
                Artifact.is_current.is_(True),
            )
        )
        assert artifact is not None
        assert len(artifact.meta_json["letter"]["closing"]) <= 120


def test_system_design_is_written_one_section_at_a_time(client, settings):
    """The outline call is small, and each subcomponent is a separate request."""
    import json

    from app.jobs.render import markdown_to_html
    from app.skills.base import SkillContext
    from app.skills.interviews import SystemDesignInterviewSkill
    from app.skills.system_design_parts import apply_section, expand_question, normalize_question

    job_id = _run(client)
    factory = get_session_factory(settings)
    with factory() as db:
        job = db.get(Job, job_id)
        ctx = SkillContext(
            job=job,
            company=None,
            settings=settings,
            llm=FakeLLMProvider(),
        )
        question = normalize_question(
            {
                "topic": "ASR serving",
                "difficulty": "core",
                "question": "Design a multilingual ASR service.",
            },
            ctx,
        )
        assert question["loaded_sections"] == []
        outline = SystemDesignInterviewSkill().render({"questions": [question]}, ctx)
        assert ":::load-design 1 requirements" in outline
        assert "Requirements" not in outline
        outline_html = markdown_to_html(outline)
        assert "data-design-load" in outline_html
        assert "Load requirements" in outline_html

        question = apply_section(
            question,
            "requirements",
            {
                "requirements": {
                    "functional": ["Transcribe audio within one request."],
                    "non_functional": ["Keep first-audio latency predictable."],
                }
            },
            ctx,
        )
        assert "requirements" in question["loaded_sections"]
        partial = SystemDesignInterviewSkill().render({"questions": [question]}, ctx)
        assert "### Requirements" in partial
        assert ":::load-design 1 entities" in partial
        assert "Load core entities" in markdown_to_html(partial)
        assert ":::load-followups 1" in partial

        section_llm = FakeLLMProvider(
            {
                "system_design_expand": json.dumps(
                    {"core_entities": [{"name": "Tenant", "fields": ["id"]}]}
                )
            }
        )
        section_ctx = SkillContext(job=job, company=None, settings=settings, llm=section_llm)
        expanded = expand_question(section_ctx, question, "entities")
        assert expanded["core_entities"][0]["name"] == "Tenant"
        assert section_llm.calls[0]["model"] == "fake-small"
        assert section_llm.calls[0]["max_tokens"] == 1000

        question = apply_section(
            question, "follow_ups", {"follow_ups": ["What happens on a language miss?"]}, ctx
        )
        assert question["follow_ups_loaded"] is True
        full = SystemDesignInterviewSkill().render({"questions": [question]}, ctx)
        assert "### Follow-ups" in full
        assert ":::load-followups 1" not in full
        assert "follow-up" in markdown_to_html(":::load-followups 2")

        artifact = db.scalar(
            select(Artifact).where(
                Artifact.job_id == job_id,
                Artifact.kind == "system_design",
                Artifact.is_current.is_(True),
            )
        )
        payload = artifact.meta_json["payload"]
        payload["questions"][0] = {
            "topic": "ASR serving",
            "difficulty": "core",
            "question": "Design a multilingual ASR service.",
            "loaded_sections": [],
        }
        artifact.meta_json = {**artifact.meta_json, "payload": payload}
        from sqlalchemy.orm.attributes import flag_modified

        flag_modified(artifact, "meta_json")
        db.commit()

    client.app.state.llm = FakeLLMProvider(
        {
            "system_design_expand": json.dumps(
                {
                    "requirements": {
                        "functional": ["Transcribe audio."],
                        "non_functional": ["Keep latency predictable."],
                    }
                }
            )
        }
    )
    response = client.post(
        f"/api/jobs/{job_id}/system-design/1/section",
        json={"section": "requirements"},
        headers=headers(client),
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert "Requirements" in data["html"]
    assert data["loaded_sections"][0] == ["requirements"]
    with factory() as db:
        artifact = db.scalar(
            select(Artifact).where(
                Artifact.job_id == job_id,
                Artifact.kind == "system_design",
                Artifact.is_current.is_(True),
            )
        )
        assert artifact.meta_json["payload"]["questions"][0]["loaded_sections"] == ["requirements"]
        assert "Transcribe audio." in artifact.content_md


class _ScriptedLLM(LLMProvider):
    """Returns each text in order, so a repair pass is observable."""

    name = "scripted"
    models = {"small": "scripted-small", "large": "scripted-large"}

    def __init__(self, texts: list[str]) -> None:
        self._texts = list(texts)
        self.calls: list[list[ChatMessage]] = []

    def complete(self, messages, **kwargs) -> LLMResponse:
        self.calls.append(list(messages))
        text = self._texts.pop(0) if self._texts else ""
        return LLMResponse(text=text, model="scripted-small")

    def health(self) -> bool:
        return True


def _unsaved_job() -> Job:
    return Job(
        title="Audio ML Engineer",
        slug="acme-audio-ml",
        source_type="text",
        raw_text="Build a multi-agent podcast production pipeline.",
        fingerprint="requirements-repair-fixture",
        source_url="https://acme.test/jobs/audio-ml",
    )


def test_requirements_section_repairs_a_missing_non_functional_list(settings):
    """Regression: the small tier folded every item into `functional` and dropped the key."""
    import json

    from app.skills.base import SkillContext
    from app.skills.system_design_parts import expand_question

    llm = _ScriptedLLM(
        [
            json.dumps(
                {
                    "requirements": {
                        "functional": [
                            "Research an episode topic from curated sources.",
                            "Persist episode state so a re-run is idempotent.",
                        ]
                    }
                }
            ),
            json.dumps(
                {
                    "requirements": {
                        "functional": ["Research an episode topic from curated sources."],
                        "non_functional": [
                            "Keep episode production idempotent per script version."
                        ],
                    }
                }
            ),
        ]
    )
    ctx = SkillContext(job=_unsaved_job(), company=None, settings=settings, llm=llm)
    expanded = expand_question(
        ctx,
        {"topic": "Podcast pipeline", "difficulty": "core", "question": "Design a podcast pipeline."},
        "requirements",
    )

    assert len(llm.calls) == 2
    repair_turn = llm.calls[1][-1].content
    assert "$.requirements.non_functional: required" in repair_turn
    assert expanded["requirements"]["non_functional"] == [
        "Keep episode production idempotent per script version."
    ]
    assert expanded["loaded_sections"] == ["requirements"]


def test_every_requirements_prompt_names_both_keys(settings):
    from app.skills.base import SkillContext
    from app.skills.interviews import CodingInterviewSkill, LowLevelDesignInterviewSkill
    from app.skills.system_design_parts import REQUIREMENTS_SHAPE, SECTION_INSTRUCTIONS

    assert "non_functional" in SECTION_INSTRUCTIONS["requirements"]
    assert "never put a non-functional item in the functional list" in REQUIREMENTS_SHAPE

    ctx = SkillContext(
        job=_unsaved_job(),
        company=None,
        settings=settings,
        llm=FakeLLMProvider(),
    )
    low_level = LowLevelDesignInterviewSkill().build_messages(ctx)[0].content
    coding = CodingInterviewSkill().build_messages(ctx)[0].content
    assert REQUIREMENTS_SHAPE in low_level
    assert "exactly two keys" in coding and "non_functional" in coding
