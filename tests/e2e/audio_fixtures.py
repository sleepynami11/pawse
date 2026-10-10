"""Synthetic audio for the browser tests: no human voice, no recordings in git.

`speechlike` is a harmonic tone with a syllable-rate envelope, loud enough that a silent or broken
capture path is obvious. Real-speech checks use human recordings from PAWSE_RECORDINGS_DIR instead.
"""
import base64
import io
import math
import struct
import wave


def speechlike(seconds=6.0, rate=48000, channels=1, peak=0.4):
    frames = bytearray()
    for i in range(int(seconds * rate)):
        t = i / rate
        envelope = 0.5 + 0.5 * math.sin(2 * math.pi * 4 * t)  # ~4 syllables per second
        tone = sum(math.sin(2 * math.pi * f * t) / n for n, f in enumerate((180, 360, 540, 720), 1))
        sample = struct.pack("<h", int(32767 * peak * envelope * tone / 2.1))
        frames += sample * channels
    return to_wav(bytes(frames), rate, channels)


def silence(seconds=1.0, rate=16000):
    return to_wav(b"\0\0" * int(seconds * rate), rate, 1)


def to_wav(frames, rate, channels):
    out = io.BytesIO()
    with wave.open(out, "wb") as f:
        f.setnchannels(channels)
        f.setsampwidth(2)
        f.setframerate(rate)
        f.writeframes(frames)
    return out.getvalue()


def read_wav(data_b64):
    """Decode a base64 WAV from a request body: (channels, sample width, rate, seconds, rms 0..1)."""
    with wave.open(io.BytesIO(base64.b64decode(data_b64))) as f:
        channels, width, rate, n = f.getnchannels(), f.getsampwidth(), f.getframerate(), f.getnframes()
        raw = f.readframes(n)
    samples = struct.unpack(f"<{len(raw) // 2}h", raw) if width == 2 else ()
    rms = math.sqrt(sum(s * s for s in samples) / len(samples)) / 32768 if samples else 0.0
    return channels, width, rate, n / rate, rms


def pcm16_rms(data_b64):
    raw = base64.b64decode(data_b64)
    samples = struct.unpack(f"<{len(raw) // 2}h", raw[: len(raw) // 2 * 2])
    return math.sqrt(sum(s * s for s in samples) / len(samples)) / 32768 if samples else 0.0


def pcm16(seconds=1.0, rate=24000):
    """Raw base64 PCM16 mono, the format Gemini Live sends model audio in."""
    with wave.open(io.BytesIO(speechlike(seconds, rate))) as f:
        return base64.b64encode(f.readframes(f.getnframes())).decode()


def speech_then_pause(speech=2.5, pause=2.5, rate=48000):
    """One spoken 'turn' then silence: the fake mic loops it, so voice-activity detection sees turns end."""
    with wave.open(io.BytesIO(speechlike(speech, rate))) as f:
        frames = f.readframes(f.getnframes())
    return to_wav(frames + b"\0\0" * int(pause * rate), rate, 1)
