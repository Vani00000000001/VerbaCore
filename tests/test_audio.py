import pytest
from pathlib import Path
from verbacore.utils.audio import get_ffmpeg_executable


def test_ffmpeg_executable_available():
    ffmpeg = get_ffmpeg_executable()
    assert ffmpeg
    assert Path(ffmpeg).is_file() or Path(ffmpeg).name.startswith("ffmpeg")
