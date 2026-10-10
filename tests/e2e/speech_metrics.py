"""Scoring transcripts of real recordings, and loading the (off-git) recordings manifest.

WER for space-separated languages, CER for Chinese. Targets are the starting bar for "the owner's
message survives transcription"; revise them in this file with measured data, not to make a run pass.
"""
import json
import os
import re
import unicodedata
from pathlib import Path

LANGUAGES = ("en", "zh", "de", "hi")
TARGETS = {"en": 0.15, "de": 0.20, "hi": 0.30, "zh": 0.20}  # WER, or CER for zh
SCRIPT = {"zh": re.compile(r"[一-鿿]"), "hi": re.compile(r"[ऀ-ॿ]")}
MIN_PER_LANGUAGE = 3


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    text = "".join(" " if unicodedata.category(c).startswith(("P", "S")) else c for c in text)
    return " ".join(text.split())


def edit_distance(ref, hyp):
    row = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        prev, row[0] = row[0], i
        for j, h in enumerate(hyp, 1):
            prev, row[j] = row[j], min(row[j] + 1, row[j - 1] + 1, prev + (r != h))
    return row[-1]


def wer(reference: str, hypothesis: str) -> float:
    ref, hyp = normalize(reference).split(), normalize(hypothesis).split()
    return edit_distance(ref, hyp) / max(len(ref), 1)


def cer(reference: str, hypothesis: str) -> float:
    ref, hyp = normalize(reference).replace(" ", ""), normalize(hypothesis).replace(" ", "")
    return edit_distance(ref, hyp) / max(len(ref), 1)


def error_rate(language: str, reference: str, hypothesis: str) -> float:
    return cer(reference, hypothesis) if language == "zh" else wer(reference, hypothesis)


def in_native_script(language: str, text: str) -> bool:
    """zh must come back in Han characters and hi in Devanagari, not romanized or translated."""
    pattern = SCRIPT.get(language)
    if not pattern:
        return True
    letters = [c for c in text if c.isalpha()]
    return bool(letters) and sum(bool(pattern.match(c)) for c in letters) / len(letters) >= 0.8


def recordings_dir() -> Path | None:
    value = os.getenv("PAWSE_RECORDINGS_DIR")
    return Path(value) if value else None


def load_manifest(directory: Path | None = None) -> list[dict]:
    """Entries {file, language, reference, speaker?, device?} from <dir>/manifest.json, or [] if absent."""
    directory = directory or recordings_dir()
    if not directory or not (directory / "manifest.json").is_file():
        return []
    entries = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))["recordings"]
    for entry in entries:
        entry["path"] = directory / entry["file"]
    return entries


def live_speech_enabled() -> str | None:
    """None when the real-recording tests may run, else the reason they skip."""
    if os.getenv("PAWSE_LIVE_SPEECH") != "1":
        return "set PAWSE_LIVE_SPEECH=1 to spend Gemini quota on real recordings"
    if not os.getenv("GEMINI_API_KEY"):
        return "GEMINI_API_KEY is not set"
    if not load_manifest():
        return "PAWSE_RECORDINGS_DIR has no manifest.json (see tests/e2e/README.md)"
    return None
