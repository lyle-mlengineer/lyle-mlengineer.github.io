"""WAV plumbing: generate a silent tone for offline use and join takes.

Providers disagree about headers, so joining is done properly: the first file's
``fmt `` chunk is kept, every ``data`` chunk is concatenated and a fresh RIFF
header is written over the result. Files whose formats disagree are rejected
rather than quietly producing noise.
"""

from __future__ import annotations

import struct

HEADER_SIZE = 44
SAMPLE_RATE = 16_000
SAMPLE_WIDTH = 2  # bytes, 16-bit PCM
CHANNELS = 1


class AudioError(ValueError):
    """Two clips could not be joined."""


def _read_chunks(data: bytes) -> list[tuple[bytes, bytes]]:
    if len(data) < 12 or data[0:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise AudioError("not a WAV file")
    chunks: list[tuple[bytes, bytes]] = []
    offset = 12
    while offset + 8 <= len(data):
        chunk_id = data[offset : offset + 4]
        (size,) = struct.unpack("<I", data[offset + 4 : offset + 8])
        body = data[offset + 8 : offset + 8 + size]
        chunks.append((chunk_id, body))
        offset += 8 + size + (size % 2)
    return chunks


def _fmt_of(data: bytes) -> bytes:
    for chunk_id, body in _read_chunks(data):
        if chunk_id == b"fmt ":
            return body
    raise AudioError("WAV file has no fmt chunk")


def _data_of(data: bytes) -> bytes:
    data_parts = [body for chunk_id, body in _read_chunks(data) if chunk_id == b"data"]
    if not data_parts:
        raise AudioError("WAV file has no data chunk")
    return b"".join(data_parts)


def wav_header(
    *,
    samples: int,
    sample_rate: int = SAMPLE_RATE,
    channels: int = CHANNELS,
    sample_width: int = SAMPLE_WIDTH,
) -> bytes:
    data_bytes = samples * channels * sample_width
    byte_rate = sample_rate * channels * sample_width
    return (
        b"RIFF"
        + struct.pack("<I", 36 + data_bytes)
        + b"WAVE"
        + b"fmt "
        + struct.pack("<IHHIIHH", 16, 1, channels, sample_rate, byte_rate, channels * sample_width, sample_width * 8)
        + b"data"
        + struct.pack("<I", data_bytes)
    )


def join_wav(parts: list[bytes]) -> bytes:
    """Concatenate WAV clips into one file with the first clip's format."""
    if not parts:
        raise AudioError("nothing to join")
    if len(parts) == 1:
        return parts[0]

    fmt = _fmt_of(parts[0])
    for part in parts[1:]:
        if _fmt_of(part) != fmt:
            raise AudioError("clips use different audio formats")

    pcm = b"".join(_data_of(part) for part in parts)
    return (
        b"RIFF"
        + struct.pack("<I", 4 + (8 + len(fmt)) + (8 + len(pcm)))
        + b"WAVE"
        + b"fmt "
        + struct.pack("<I", len(fmt))
        + fmt
        + b"data"
        + struct.pack("<I", len(pcm))
        + pcm
    )


def tone_wav(seconds: float, *, frequency: float = 220.0, volume: float = 0.15) -> bytes:
    """A short mono tone. The offline provider uses it so takes are playable."""
    frames = int(SAMPLE_RATE * max(0.05, min(seconds, 8.0)))
    samples = bytearray()
    for index in range(frames):
        value = volume * ((index % 64) - 32) / 32
        envelope = 1.0 - (index / frames) * 0.4
        sample = int(32767 * value * envelope)
        samples += struct.pack("<h", sample)
    return wav_header(samples=frames) + bytes(samples)


def duration_ms(wav: bytes) -> int:
    """Length of a WAV clip in milliseconds, computed from its data chunk."""
    try:
        fmt = _fmt_of(wav)
        byte_rate = struct.unpack("<I", fmt[8:12])[0]
        data_bytes = len(_data_of(wav))
    except AudioError:
        return 0
    if not byte_rate:
        return 0
    return int(round(data_bytes / byte_rate * 1000))


def pcm_to_wav(
    pcm: bytes,
    *,
    sample_rate: int = 16_000,
    channels: int = 1,
    sample_width: int = 2,
) -> bytes:
    """Wrap headerless 16-bit PCM in a WAV container.

    ElevenLabs can return raw PCM, which is cheaper and lossless to wrap than
    decoding MP3 just to re-encode it.
    """
    samples = len(pcm) // max(1, channels * sample_width)
    return (
        wav_header(samples=samples, sample_rate=sample_rate, channels=channels, sample_width=sample_width)
        + pcm[: samples * channels * sample_width]
    )
