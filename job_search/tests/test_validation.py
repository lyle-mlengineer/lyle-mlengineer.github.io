from __future__ import annotations

import pytest

from app.validation import ValidationError, is_valid, validate

SCHEMA = {
    "type": "object",
    "required": ["summary", "skills", "fit_score"],
    "properties": {
        "summary": {"type": "string", "min_len": 10},
        "skills": {"type": "array", "items": {"type": "string"}},
        "fit_score": {"type": "number"},
        "remote": {"type": "boolean", "nullable": True},
        "seniority": {"type": "string", "enum": ["junior", "mid", "senior"]},
    },
}


def test_accepts_a_complete_payload():
    payload = {
        "summary": "A role focused on speech recognition.",
        "skills": ["PyTorch", "ONNX"],
        "fit_score": 8.5,
        "remote": True,
        "seniority": "senior",
    }
    validate(payload, SCHEMA)


def test_reports_every_missing_required_field():
    with pytest.raises(ValidationError) as excinfo:
        validate({"skills": []}, SCHEMA)
    errors = excinfo.value.errors
    assert any("summary" in error for error in errors)
    assert any("fit_score" in error for error in errors)


def test_rejects_wrong_types_and_bool_as_number():
    assert not is_valid({**valid(), "fit_score": "high"}, SCHEMA)
    assert not is_valid({**valid(), "fit_score": True}, SCHEMA)
    assert is_valid({**valid(), "fit_score": 7}, SCHEMA)


def test_enum_and_min_length():
    with pytest.raises(ValidationError) as excinfo:
        validate({**valid(), "summary": "short", "seniority": "principal"}, SCHEMA)
    assert any("shorter" in error for error in excinfo.value.errors)
    assert any("one of" in error for error in excinfo.value.errors)


def test_nullable_allows_none():
    validate({**valid(), "remote": None}, SCHEMA)


def test_nested_items_are_checked():
    with pytest.raises(ValidationError) as excinfo:
        validate({**valid(), "skills": ["PyTorch", 3]}, SCHEMA)
    assert any("$.skills[1]" in error for error in excinfo.value.errors)


def test_unknown_properties_are_allowed():
    validate({**valid(), "extra": "ignored"}, SCHEMA)


def valid() -> dict:
    return {
        "summary": "A role focused on speech recognition.",
        "skills": ["PyTorch"],
        "fit_score": 8.5,
        "remote": True,
        "seniority": "senior",
    }
