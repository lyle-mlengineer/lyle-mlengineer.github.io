from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.models import Company, Job
from app.providers.llm.fake import FakeLLMProvider
from app.skills.base import SkillContext
from app.skills.company_research import CompanyResearchSkill
from app.skills.registry import FAKE_RESPONSES


def _context(settings, company: Company, llm: FakeLLMProvider) -> SkillContext:
    job = Job(
        title="Senior Machine Learning Engineer",
        slug="senior-ml-engineer-acme",
        source_type="text",
        raw_text="Acme Speech builds multilingual voice models. Python and PyTorch required.",
        fingerprint="research-test",
    )
    return SkillContext(job=job, company=company, settings=settings, llm=llm)


def test_company_research_is_reused_while_the_brief_is_fresh(settings, monkeypatch):
    monkeypatch.setattr(settings, "research_ttl_days", 30)
    company = Company(name="Acme Speech", slug="acme-speech", domain="acme.example")
    llm = FakeLLMProvider(FAKE_RESPONSES)
    skill = CompanyResearchSkill()
    ctx = _context(settings, company, llm)

    first = skill.execute(ctx)
    assert first.response.model == "fake-large"
    assert company.researched_at
    assert company.research_json
    assert company.summary == first.payload["summary"]
    assert company.industry == first.payload["industry"]
    assert company.headcount == first.payload["size"]

    llm.calls.clear()
    second = skill.execute(_context(settings, company, llm))
    assert second.response.model == "company-research-cache"
    assert second.payload["cached"] is True
    assert second.payload["summary"] == first.payload["summary"]
    assert llm.calls == []
    assert company.researched_at is not None


def test_stale_company_research_is_refreshed(settings, monkeypatch):
    monkeypatch.setattr(settings, "research_ttl_days", 30)
    company = Company(
        name="Acme Speech",
        slug="acme-speech",
        research_json={"summary": "old brief", "sources": [], "open_questions": []},
        researched_at=(datetime.now(UTC) - timedelta(days=31)).isoformat().replace("+00:00", "Z"),
    )
    llm = FakeLLMProvider(FAKE_RESPONSES)
    result = CompanyResearchSkill().execute(_context(settings, company, llm))
    assert result.response.model == "fake-large"
    assert llm.calls
    assert result.payload["summary"] != "old brief"


def test_zero_ttl_always_researches(settings, monkeypatch):
    monkeypatch.setattr(settings, "research_ttl_days", 0)
    company = Company(
        name="Acme Speech",
        slug="acme-speech",
        research_json={"summary": "cached brief", "sources": [], "open_questions": []},
        researched_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    )
    llm = FakeLLMProvider(FAKE_RESPONSES)
    result = CompanyResearchSkill().execute(_context(settings, company, llm))
    assert result.response.model == "fake-large"
    assert llm.calls
