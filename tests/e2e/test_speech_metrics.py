import json

import pytest

from speech_metrics import TARGETS, LANGUAGES, cer, error_rate, in_native_script, load_manifest, normalize, wer


def test_normalize_ignores_case_punctuation_and_width():
    assert normalize("  Meine KATZE hinkt!  ") == "meine katze hinkt"
    assert normalize("我的猫，跛了。") == normalize("我的猫 跛了")
    assert normalize("ＭＩＭＩ") == "mimi"


def test_wer_counts_substitutions_insertions_and_deletions():
    assert wer("my cat is limping", "my cat is limping") == 0
    assert wer("my cat is limping", "my cat limping") == 0.25
    assert wer("my cat is limping", "my dog is limping badly") == 0.5
    assert wer("", "") == 0


def test_chinese_is_scored_by_character():
    assert cer("我的猫在跳下来后跛行", "我的猫在跳下来后跛行。") == 0
    assert cer("我的猫跛行", "我的狗跛行") == 0.2
    assert error_rate("zh", "我的猫跛行", "我的狗跛行") == 0.2
    assert error_rate("en", "a b c d e", "a b c d x") == 0.2


@pytest.mark.parametrize("language,text,expected", [
    ("zh", "我的猫在跛行", True),
    ("zh", "wo de mao", False),
    ("hi", "मेरी बिल्ली लंगड़ा रही है", True),
    ("hi", "meri billi langda rahi hai", False),
    ("hi", "My cat is limping", False),
    ("de", "Meine Katze hinkt", True),
])
def test_native_script_check_catches_romanized_or_translated_output(language, text, expected):
    assert in_native_script(language, text) is expected


def test_every_language_has_a_target():
    assert set(TARGETS) == set(LANGUAGES)


def test_manifest_loads_entries_with_paths(tmp_path):
    (tmp_path / "manifest.json").write_text(json.dumps({"recordings": [
        {"file": "de-01.wav", "language": "de", "reference": "Meine Katze hinkt."}]}))
    [entry] = load_manifest(tmp_path)
    assert entry["path"] == tmp_path / "de-01.wav" and entry["language"] == "de"
    assert load_manifest(tmp_path / "missing") == []
