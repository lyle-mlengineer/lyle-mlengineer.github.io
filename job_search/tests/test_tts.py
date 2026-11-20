"""The speech layer: chunking, WAV joining, and each provider's wire format."""

from __future__ import annotations

import httpx
import pytest

from app.providers.tts.audio import duration_ms, join_wav, pcm_to_wav, tone_wav
from app.providers.tts.base import TTSProviderError, chunk_text
from app.providers.tts.breeze import BreezeProvider
from app.providers.tts.elevenlabs import ElevenLabsProvider
from app.providers.tts.fake import FakeTTSProvider
from app.providers.tts.orpheus import OrpheusProvider
from app.providers.tts.pricing import is_priced, speech_cost
from app.providers.tts.registry import build_tts_provider, search_voices


def test_chunk_text_keeps_sentences_and_never_splits_words():
    text = "First sentence here. Second sentence is longer than the rest. Third one."
    chunks = chunk_text(text, 40)
    assert all(len(chunk) <= 40 for chunk in chunks)
    assert " ".join(chunks).split() == text.split()
    assert chunk_text("", 40) == []
    assert chunk_text("short", 40) == ["short"]


def test_chunk_text_falls_back_to_words_for_a_monster_sentence():
    text = "word " * 200
    chunks = chunk_text(text, 50)
    assert all(len(chunk) <= 50 for chunk in chunks)
    assert all(chunk.strip() for chunk in chunks)


def test_join_wav_keeps_one_header_and_one_data_chunk():
    first = tone_wav(0.5, frequency=200)
    second = tone_wav(0.5, frequency=300)
    joined = join_wav([first, second])
    assert joined[:4] == b"RIFF"
    assert joined.count(b"data") == 1
    assert duration_ms(joined) > duration_ms(first)


def test_join_wav_refuses_mismatched_formats():
    mono = tone_wav(0.2)
    stereo = pcm_to_wav(b"\x00\x01" * 100, channels=2)
    with pytest.raises(ValueError):
        join_wav([mono, stereo])


def test_fake_provider_speaks_the_whole_text_and_records_the_call():
    provider = FakeTTSProvider()
    speech = provider.synthesize("A" * 400, voice="fake-answerer", direction=["warm"])
    assert speech.format == "wav"
    assert speech.chars == 400
    assert speech.requests == 3  # 190 characters per request
    assert duration_ms(speech.audio) > 0
    assert provider.calls[0]["direction"] == ["warm"]


def test_fake_provider_clones_a_reference_that_exists(tmp_path):
    provider = FakeTTSProvider()
    sample = tmp_path / "reference.wav"
    sample.write_bytes(tone_wav(0.3))
    assert provider.clone_reference(str(sample)) == "fake-reference"


def test_speech_pricing_and_which_providers_are_priced():
    assert speech_cost("orpheus", 1_000_000) == 22.0
    assert speech_cost("fake", 1_000) == 0.0
    assert speech_cost("breeze", 10_000) == 0.0
    assert is_priced("elevenlabs") and not is_priced("breeze")


def test_search_voices_matches_text_and_filters():
    voices = FakeTTSProvider().voices()
    assert [voice.id for voice in search_voices(voices, gender="male")] == [
        "fake-interviewer-alt",
        "fake-answerer-alt",
    ]
    assert [voice.id for voice in search_voices(voices, query="bright")] == ["fake-answerer"]
    assert search_voices(voices, query="nothing-like-this") == []


def test_registry_prefers_a_configured_key_and_falls_back_to_offline(settings):
    offline = settings.model_copy(
        update={"tts_provider": "auto", "groq_api_key": "", "elevenlabs_api_key": "", "breeze_api_key": ""}
    )
    assert build_tts_provider(offline).name == "fake"

    configured = settings.model_copy(update={"tts_provider": "orpheus", "groq_api_key": "gsk_test"})
    assert build_tts_provider(configured).name == "orpheus"

    auto = offline.model_copy(update={"breeze_api_key": "brz_test", "groq_api_key": "gsk_test"})
    assert build_tts_provider(auto).name == "breeze"


def test_orpheus_shapes_the_request_and_carries_tags_into_every_chunk():
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(
            {
                "url": str(request.url),
                "auth": request.headers.get("authorization"),
                "body": __import__("json").loads(request.content),
            }
        )
        return httpx.Response(200, content=tone_wav(0.2))

    provider = OrpheusProvider(
        "gsk_test",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    speech = provider.synthesize("One. " * 100, voice="hannah", direction=["confident", "steady"])

    assert speech.requests == len(seen) > 1
    assert seen[0]["url"] == "https://api.groq.com/openai/v1/audio/speech"
    assert seen[0]["auth"] == "Bearer gsk_test"
    assert seen[0]["body"]["model"] == "canopylabs/orpheus-v1-english"
    assert seen[0]["body"]["response_format"] == "wav"
    assert seen[0]["body"]["input"].startswith("[confident steady] ")
    assert all(entry["body"]["input"].startswith("[confident steady]") for entry in seen)
    assert all(len(entry["body"]["input"]) <= 200 for entry in seen)


def test_orpheus_rejects_an_unknown_voice_before_spending_a_request():
    provider = OrpheusProvider("gsk_test", client=httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, content=tone_wav(0.2))
    )))
    with pytest.raises(TTSProviderError):
        provider.synthesize("hello", voice="not-a-voice")


def test_orpheus_reports_the_provider_message():
    provider = OrpheusProvider(
        "gsk_test",
        client=httpx.Client(transport=httpx.MockTransport(
            lambda request: httpx.Response(400, json={"error": {"message": "model gated"}})
        )),
    )
    with pytest.raises(TTSProviderError, match="model gated"):
        provider.synthesize("hello", voice="hannah")


def test_elevenlabs_wraps_pcm_and_reads_the_catalogue():
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url.path == "/v2/voices":
            return httpx.Response(200, json={"voices": [
                {
                    "voice_id": "v1",
                    "name": "Ada",
                    "labels": {"gender": "female", "accent": "british", "description": "calm and clear"},
                    "preview_url": "https://example.test/ada.mp3",
                    "category": "premade",
                }
            ]})
        return httpx.Response(200, content=b"\x00\x01" * 800)

    provider = ElevenLabsProvider(
        "sk_test", client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    voices = provider.voices()
    assert voices[0].id == "v1"
    assert voices[0].gender == "female"
    assert voices[0].clonable is True

    speech = provider.synthesize("Hello there.", voice="v1", direction=["warm"])
    assert speech.audio[:4] == b"RIFF"
    tts_calls = [call for call in calls if call.url.path.startswith("/v1/text-to-speech")]
    assert tts_calls[0].url.params["output_format"] == "pcm_16000"
    assert tts_calls[0].headers["xi-api-key"] == "sk_test"
    body = __import__("json").loads(tts_calls[0].content)
    assert body["voice_settings"]["style"] == 0.35  # warm asks for performance


def test_elevenlabs_clones_an_upload_and_returns_the_voice_id(tmp_path):
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"voice_id": "cloned-123"})

    sample = tmp_path / "me.wav"
    sample.write_bytes(tone_wav(0.4))
    provider = ElevenLabsProvider("sk_test", client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert provider.clone_reference(str(sample), name="Lyle") == "cloned-123"
    assert seen[0].url.path == "/v1/voices/add"
    assert b"Lyle" in seen[0].content


def test_breeze_sends_wav_output_and_audio_tags():
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append({"path": request.url.path, "query": request.url.params, "body": __import__("json").loads(request.content)})
        return httpx.Response(200, content=tone_wav(0.2))

    provider = BreezeProvider("brz_test", client=httpx.Client(transport=httpx.MockTransport(handler)))
    speech = provider.synthesize("Hello.", voice="b-voice", direction=["measured"])
    assert speech.format == "wav"
    assert seen[0]["path"] == "/v1/text-to-speech/b-voice"
    assert seen[0]["query"]["output_format"] == "wav"
    assert seen[0]["body"]["text"].startswith("[measured] ")


def test_breeze_clone_is_two_steps_and_saves_the_voice(tmp_path):
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        if request.url.path == "/v1/voice-previews/clone":
            return httpx.Response(200, json={"generated_voice_id": "gen-1"})
        return httpx.Response(200, json={"voice_id": "saved-9"})

    sample = tmp_path / "me.wav"
    sample.write_bytes(tone_wav(0.4))
    provider = BreezeProvider("brz_test", client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert provider.clone_reference(str(sample), name="Me") == "saved-9"
    assert seen == ["/v1/voice-previews/clone", "/v1/voice-previews/gen-1/save"]


def test_breeze_catalogue_maps_labels_to_a_voice():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"voices": [
            {"voice_id": "b1", "name": "Bay", "gender": "female", "accent": "us_west",
             "tone": ["warm", "calm"], "language_code": "en"}
        ]})

    provider = BreezeProvider("brz_test", client=httpx.Client(transport=httpx.MockTransport(handler)))
    voice = provider.voices()[0]
    assert voice.id == "b1"
    assert voice.gender == "female"
    assert voice.accent == "us west"
    assert voice.tags == ("warm", "calm")
    assert "warm" in voice.description
