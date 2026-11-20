"""The interview audio tab: turn planning, generation, playback and cloning."""

from __future__ import annotations

from sqlalchemy import select

from app.db import get_session_factory
from app.jobs.dialogue import build_turns, direction_from_notes
from app.jobs.render import markdown_to_html
from app.models import AudioTake, Job
from app.providers.tts.audio import tone_wav
from tests.conftest import login

TEXT = """\
Senior Machine Learning Engineer at Acme Speech.
We are looking for a senior engineer to own speech recognition quality across six languages.
You will build evaluation tooling, fine-tune Whisper models and work with product teams.
Must have Python, PyTorch and hands-on ASR experience. Remote within Europe.
"""


def headers(client) -> dict[str, str]:
    return {"X-CSRF-Token": client.get("/api/auth/me").json()["csrf_token"]}


def _job_with_pack(client) -> int:
    login(client)
    response = client.post(
        "/api/jobs", json={"source_text": TEXT}, headers=headers(client)
    )
    assert response.status_code == 202, response.text
    return response.json()["job_id"]


def test_direction_notes_map_onto_delivery_words():
    assert direction_from_notes(
        ["Pause after the evaluation sentence."], fallback=("warm",)
    ) == ("steady",)
    assert direction_from_notes(["Own the result, be direct."], fallback=("warm",)) == (
        "confident",
    )
    assert direction_from_notes([], fallback=("warm", "confident")) == (
        "warm",
        "confident",
    )


def test_build_turns_alternates_and_carries_the_question_and_direction():
    turns = build_turns(
        {
            "tell_me_about_yourself": {
                "answer": "I am a speech engineer.",
                "delivery_notes": ["Pause after the metrics."],
            }
        }
    )
    assert [turn.role for turn in turns] == ["interviewer", "interviewee"]
    assert turns[0].text == "To start, tell me about yourself."
    assert turns[1].text == "I am a speech engineer."
    assert turns[0].kind == turns[1].kind == "tell_me_about_yourself"
    assert "steady" in turns[1].direction


def test_build_turns_reads_system_design_and_coding_banks():
    turns = build_turns(
        {
            "system_design": {
                "questions": [
                    {
                        "topic": "Serving",
                        "difficulty": "deep",
                        "question": "Design the serving path.",
                        "answer": "I would start with the contract.",
                    }
                ]
            },
            "coding": {
                "problems": [
                    {
                        "topic": "Intervals",
                        "difficulty": "core",
                        "question": "Merge the segments.",
                        "answer": "Sort by start, then merge in one pass.",
                    }
                ]
            },
        },
        max_turns=10,
    )
    assert [turn.kind for turn in turns] == ["system_design", "system_design", "coding", "coding"]
    assert turns[0].text == "Design the serving path."
    assert turns[1].section == "Serving"
    assert turns[2].text == "Merge the segments."
    assert turns[3].section == "Intervals"


def test_long_answers_are_broken_into_scannable_paragraphs():
    answer = " ".join(
        f"Sentence {index} explains a different part of the answer in enough words to matter."
        for index in range(1, 15)
    )
    html = markdown_to_html(f"# Answer\n\n{answer}\n", paragraph_chars=240)
    paragraphs = [block for block in html.split("\n") if block.startswith("<p>")]
    assert len(paragraphs) > 3
    assert all(len(block) < 400 for block in paragraphs)
    assert "Sentence 14" in paragraphs[-1]
    # Short paragraphs and headings are untouched.
    assert markdown_to_html("# Title\n\nShort.", paragraph_chars=240).count("<p>") == 1


def test_job_page_exposes_the_script_and_audio_tabs(client):
    job_id = _job_with_pack(client)
    page = client.get(f"/jobs/{job_id}").text
    assert 'id="tab-script"' in page
    assert 'id="tab-audio"' in page
    assert 'data-panel="audio"' in page
    assert "data-audio-studio" in page
    assert 'data-picker="interviewer"' in page
    assert 'data-picker="interviewee"' in page
    assert 'data-voice-modal' in page
    assert 'data-voice-open' in page
    assert 'data-voice-apply' in page
    assert 'class="voice-summary"' in page
    assert "data-voice-search" in page
    assert "data-voice-gender" in page
    assert "data-voice-ethnicity" in page
    assert "data-voice-sample" in page
    assert "data-audio-generate" in page
    assert "data-audio-scope" in page
    assert "data-hear-section" in page
    assert "file-field__input" in page
    assert 'data-scope-title="Proud project"' not in page  # title is "A project I am proud of"
    assert 'data-hear-section="proud_project"' in page
    assert 'data-hear-section="system_design"' in page
    assert 'data-hear-section="coding"' in page
    assert 'data-scope-title="System design"' in page
    assert 'data-scope-title="Coding interview"' in page


def test_voice_catalogue_describes_and_filters_voices(client):
    login(client)
    body = client.get("/api/tts/voices").json()
    assert body["provider"] == "fake"
    assert body["count"] == body["total"] == 4
    voice = body["voices"][0]
    assert voice["description"] and voice["gender"] and voice["ethnicity"] is not None
    assert body["defaults"]["interviewer"] and body["defaults"]["interviewee"]

    male = client.get("/api/tts/voices", params={"gender": "male"}).json()
    assert male["count"] == 2
    searched = client.get("/api/tts/voices", params={"q": "bright"}).json()
    assert [item["name"] for item in searched["voices"]] == ["Junie"]


def test_a_sample_is_served_as_playable_wav(client):
    login(client)
    response = client.get("/api/tts/voices/fake-interviewer/sample")
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    assert response.content[:4] == b"RIFF"
    assert len(response.content) > 1_000


def test_a_scoped_take_only_speaks_the_requested_section(client, settings):
    job_id = _job_with_pack(client)
    response = client.post(
        f"/api/jobs/{job_id}/audio",
        json={
            "interviewer": "fake-interviewer",
            "interviewee": "fake-answerer",
            "kind": "proud_project",
        },
        headers=headers(client),
    )
    assert response.status_code == 202, response.text

    take = client.get(
        f"/api/jobs/{job_id}/audio", params={"kind": "proud_project"}
    ).json()["take"]
    assert take is not None
    assert take["turns"]
    assert take["scope"] == "proud_project"
    assert {turn["kind"] for turn in take["turns"]} == {"proud_project"}
    assert {turn["role"] for turn in take["turns"]} == {"interviewer", "interviewee"}

    page = client.get(f"/jobs/{job_id}").text
    assert 'data-take-scope="proud_project"' in page

    other = client.get(
        f"/api/jobs/{job_id}/audio", params={"kind": "work_history"}
    ).json()["take"]
    assert other is None

    bad = client.get(f"/api/jobs/{job_id}/audio", params={"kind": "not_a_section"})
    assert bad.status_code == 400


def test_a_take_speaks_every_turn_and_serves_each_wav(client, settings):
    job_id = _job_with_pack(client)
    response = client.post(
        f"/api/jobs/{job_id}/audio",
        json={"interviewer": "fake-interviewer", "interviewee": "fake-answerer"},
        headers=headers(client),
    )
    assert response.status_code == 202, response.text

    take = client.get(f"/api/jobs/{job_id}/audio").json()["take"]
    assert take["status"] == "ready", take
    assert take["turns"], "the pack produced no turns"
    assert take["ready_turns"] == len(take["turns"])
    roles = {turn["role"] for turn in take["turns"]}
    assert roles == {"interviewer", "interviewee"}
    assert all(turn["audio_url"] for turn in take["turns"])
    assert all(isinstance(turn["paragraphs"], list) for turn in take["turns"])
    assert max(len(turn["paragraphs"]) for turn in take["turns"]) > 1

    first = take["turns"][0]
    assert first["role"] == "interviewer"
    assert first["direction"]
    audio = client.get(first["audio_url"])
    assert audio.status_code == 200
    assert audio.content[:4] == b"RIFF"

    page = client.get(f"/jobs/{job_id}").text
    assert "turn--interviewer" in page and "turn__audio" in page
    assert "turn__player" in page
    assert "audio-player__toggle" in page
    assert "audio-player__track" in page
    assert "audio-player__time" in page
    assert "<audio class=\"turn__audio\" controls" not in page
    assert page.count('class="turn__text"') > len(take["turns"])

    factory = get_session_factory(settings)
    with factory() as db:
        job = db.get(Job, job_id)
        assert job is not None
        stored = db.scalar(select(AudioTake).where(AudioTake.job_id == job_id))
        assert stored is not None and stored.provider == "fake"


def test_reference_recording_is_cloned_and_used_for_the_answers(client, settings):
    login(client)
    response = client.post(
        "/api/voices/reference",
        files={"file": ("me.wav", tone_wav(0.4), "audio/wav")},
        headers=headers(client),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["saved"] is True
    assert body["cloned"] is True
    assert body["cloned_voice"] == "fake-reference"

    status = client.get("/api/voices/reference").json()
    assert status["exists"] and status["cloned_voice"] == "fake-reference"

    job_id = _job_with_pack(client)
    response = client.post(
        f"/api/jobs/{job_id}/audio",
        json={"interviewer": "fake-interviewer", "interviewee": "fake-answerer"},
        headers=headers(client),
    )
    assert response.status_code == 202, response.text

    factory = get_session_factory(settings)
    with factory() as db:
        take = db.scalar(select(AudioTake).where(AudioTake.job_id == job_id))
        assert take is not None
        assert take.reference_voice == "fake-reference"


def test_a_second_take_is_refused_while_one_is_in_flight(client, settings):
    job_id = _job_with_pack(client)
    first = client.post(
        f"/api/jobs/{job_id}/audio",
        json={"interviewer": "fake-interviewer", "interviewee": "fake-answerer"},
        headers=headers(client),
    )
    assert first.status_code == 202

    # The background task has already finished, so force one back into flight.
    factory = get_session_factory(settings)
    with factory() as db:
        take = db.scalar(select(AudioTake).where(AudioTake.job_id == job_id))
        assert take is not None
        take.status = "generating"
        db.commit()

    second = client.post(
        f"/api/jobs/{job_id}/audio",
        json={"interviewer": "fake-interviewer", "interviewee": "fake-answerer"},
        headers=headers(client),
    )
    assert second.status_code == 409
    assert "already being generated" in second.json()["error"]["message"]
