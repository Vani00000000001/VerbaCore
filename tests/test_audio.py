import struct
import wave
import pytest
from pathlib import Path
from verbacore.utils.audio import get_ffmpeg_executable, get_audio_duration_seconds, convert_audio_to_mp3


def test_ffmpeg_executable_available():
    ffmpeg = get_ffmpeg_executable()
    assert ffmpeg
    assert Path(ffmpeg).is_file() or Path(ffmpeg).name.startswith("ffmpeg")


def test_audio_duration_and_mp3_conversion(tmp_path):
    wav_path = tmp_path / "tone.wav"
    with wave.open(str(wav_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(struct.pack("<" + "h" * 4000, *([0] * 4000)))  # 0.25s silence

    dur = get_audio_duration_seconds(wav_path)
    assert 0.2 <= dur <= 0.35

    mp3_path = convert_audio_to_mp3(wav_path, tmp_path / "tone.mp3", title="Test Tone")
    assert mp3_path.is_file()
    assert mp3_path.stat().st_size > 100

