import json
import urllib.request

from verbacore.config import AppConfig
from verbacore.llm import cloud


class _DummyResp:
    def __init__(self, payload: dict, status: int = 200):
        self._bytes = json.dumps(payload).encode("utf-8")
        self.status = status

    def read(self):
        return self._bytes

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_cloud_connection_validation():
    ok, msg = cloud.test_cloud_connection("gemini", "   ")
    assert not ok
    assert "empty" in msg.lower()


def test_gemini_empty_segments_uses_actual_duration(tmp_path, monkeypatch):
    audio = tmp_path / "empty.wav"
    audio.write_bytes(b"RIFF")

    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda req, timeout=120: _DummyResp(
            {"candidates": [{"content": {"parts": [{"text": json.dumps({"segments": []})}]}}]}
        ),
    )
    monkeypatch.setattr("verbacore.utils.audio.get_audio_duration_seconds", lambda p: 42.5)

    segs, _langs, dur, _ = cloud.transcribe_with_gemini(audio, "fake-key")
    assert segs == []
    assert dur == 42.5


def test_groq_cloud_does_not_autostart_local_llm(tmp_path, monkeypatch):
    audio = tmp_path / "sample.wav"
    audio.write_bytes(b"RIFF")

    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda req, timeout=60: _DummyResp(
            {
                "duration": 5.0,
                "language": "en",
                "segments": [{"start": 0.0, "end": 2.0, "text": "Hello cloud."}],
            }
        ),
    )

    called = {}

    def fake_brain(segments, dur, config=None, auto_start=True):
        called["auto_start"] = auto_start
        return {
            "is_multi_speaker": False,
            "speaker_count": 1,
            "languages": ["EN"],
            "executive_summary": "Short test summary.",
            "key_takeaways": ["Point"],
            "action_items": ["None"],
        }

    monkeypatch.setattr(cloud, "analyze_conversation_with_brain_llm", fake_brain)
    segs, _langs, dur, _ = cloud.transcribe_with_groq(audio, "fake-key", config=AppConfig())
    assert called["auto_start"] is False
    assert dur == 5.0
    assert len(segs) == 1
