"""Keep tests away from the local owner's private voice configuration."""
import pytest


@pytest.fixture(autouse=True)
def private_voice_store(monkeypatch, tmp_path):
    monkeypatch.setenv('PAWSE_VOICE_PROFILE_PATH', str(tmp_path / 'voice.json'))


@pytest.fixture(autouse=True)
def no_local_clinic_snapshot(monkeypatch, tmp_path):
    # The OSM snapshot in tmp/ is private runtime data; tests must not depend on it.
    monkeypatch.setenv('PAWSE_CLINIC_SNAPSHOT', str(tmp_path / 'no-snapshot.json'))
