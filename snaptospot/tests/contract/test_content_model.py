import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas.content import ContentModel

FIXTURE = Path(__file__).parents[1] / "fixtures" / "content_model.json"


def _payload() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_fixture_content_model_validates() -> None:
    model = ContentModel.model_validate(_payload())
    assert [fact.key for fact in model.facts][:2] == ["asr.wer", "work.projects"]
    assert model.quote is not None
    assert model.proof[0].emphasis == "lead"
    assert model.offerings[0].metric_fact_id == "f_01"


def test_fact_without_source_quote_fails() -> None:
    payload = _payload()
    payload["facts"][0]["source_quote"] = ""
    with pytest.raises(ValidationError):
        ContentModel.model_validate(payload)


def test_tier_c_fact_cannot_be_referenced_by_proof() -> None:
    payload = _payload()
    payload["facts"].append(
        {
            "id": "f_04",
            "key": "asr.reported",
            "value": "20",
            "unit": "% WER",
            "label": "reported word error rate",
            "source_type": "web",
            "source": "https://news.example.com/asr",
            "source_quote": "a reported 20% word error rate",
            "tier": "C",
            "retrieved_at": "2026-11-14",
        }
    )
    payload["proof"].append({"fact_id": "f_04", "emphasis": "normal"})
    with pytest.raises(ValidationError):
        ContentModel.model_validate(payload)


def test_quote_requires_permission() -> None:
    payload = _payload()
    del payload["facts"][2]["permission"]
    with pytest.raises(ValidationError):
        ContentModel.model_validate(payload)


def test_unsupported_digit_in_free_text_fails() -> None:
    payload = copy.deepcopy(_payload())
    payload["offerings"][0]["one_liner"] = "Ships 2x faster than the baseline."
    with pytest.raises(ValidationError):
        ContentModel.model_validate(payload)
