"""Keep tests away from the local owner's private voice configuration."""
import pytest


@pytest.fixture(autouse=True)
def private_voice_store(monkeypatch, tmp_path):
    monkeypatch.setenv('PAWSE_VOICE_PROFILE_PATH', str(tmp_path / 'voice.json'))
