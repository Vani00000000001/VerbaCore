import os
import re
import shutil
import subprocess
import uuid
from pathlib import Path

try:
    import imageio_ffmpeg
except ImportError:
    imageio_ffmpeg = None

FFMPEG_PROBE_TIMEOUT_SECONDS = 60
FFMPEG_TIMEOUT_SECONDS = 3600


def get_ffmpeg_executable() -> str:
    """Find FFmpeg binary on PATH or via imageio_ffmpeg."""
    if system_ffmpeg := shutil.which("ffmpeg"):
        return system_ffmpeg
    if imageio_ffmpeg is not None:
        return imageio_ffmpeg.get_ffmpeg_exe()
    raise RuntimeError(
        "FFmpeg is required for audio processing. Please install ffmpeg on your system PATH "
        "or install imageio-ffmpeg: pip install imageio-ffmpeg"
    )


def get_audio_duration_seconds(audio_path: Path) -> float:
    """Accurately measure the duration of an audio file using FFmpeg."""
    ffmpeg_path = get_ffmpeg_executable()
    try:
        result = subprocess.run(
            [ffmpeg_path, "-hide_banner", "-i", str(audio_path)],
            capture_output=True,
            text=True,
            timeout=FFMPEG_PROBE_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as ex:
        raise RuntimeError(f"Could not inspect recording duration: {ex}") from ex

    match = re.search(r"Duration: (\d+):(\d+):([\d.]+)", result.stderr)
    if match:
        hours, minutes, seconds = match.groups()
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)

    # Fallback to decode stream
    try:
        result = subprocess.run(
            [
                ffmpeg_path,
                "-hide_banner",
                "-nostats",
                "-i",
                str(audio_path),
                "-map",
                "0:a:0",
                "-progress",
                "pipe:1",
                "-f",
                "null",
                "-",
            ],
            capture_output=True,
            text=True,
            timeout=FFMPEG_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as ex:
        raise RuntimeError(f"Could not measure recording duration: {ex}") from ex

    if result.returncode != 0:
        details = result.stderr.strip().splitlines()
        reason = details[-1] if details else "FFmpeg could not decode the audio"
        raise RuntimeError(f"Could not measure recording duration: {reason}")

    match = re.search(r"^out_time_us=(\d+)$", result.stdout, re.MULTILINE)
    if not match:
        raise RuntimeError("FFmpeg decoded the recording but did not report its duration")

    duration = int(match.group(1)) / 1_000_000
    if duration <= 0:
        raise RuntimeError("The recording contains no measurable audio")
    return duration


def convert_audio_to_mp3(source_path: Path, target_mp3: Path, title: str | None = None) -> Path:
    """Convert source audio (e.g. webm/wav) into high quality MP3."""
    ffmpeg_path = get_ffmpeg_executable()
    temp_mp3 = target_mp3.with_suffix(f".tmp-{os.getpid()}-{uuid.uuid4().hex[:8]}.mp3")
    cmd = [
        ffmpeg_path,
        "-y",
        "-i",
        str(source_path),
        "-map",
        "0:a:0",
        "-vn",
        "-codec:a",
        "libmp3lame",
        "-b:a",
        "128k",
        "-id3v2_version",
        "3",
    ]
    if title:
        cmd.extend(["-metadata", f"title={title}"])
    cmd.append(str(temp_mp3))

    try:
        subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            timeout=FFMPEG_TIMEOUT_SECONDS,
        )
        temp_mp3.replace(target_mp3)
    except (OSError, subprocess.SubprocessError) as ex:
        temp_mp3.unlink(missing_ok=True)
        raise RuntimeError(f"Could not convert recording to MP3: {ex}") from ex

    return target_mp3


def segment_audio(source_path: Path, output_pattern: str, chunk_seconds: int = 600) -> None:
    """Segment long audio into smaller MP3 chunks for cloud or processing."""
    ffmpeg_path = get_ffmpeg_executable()
    try:
        subprocess.run(
            [
                ffmpeg_path,
                "-y",
                "-i",
                str(source_path),
                "-map",
                "0:a:0",
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-codec:a",
                "libmp3lame",
                "-b:a",
                "64k",
                "-f",
                "segment",
                "-segment_time",
                str(chunk_seconds),
                "-reset_timestamps",
                "1",
                output_pattern,
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=FFMPEG_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError) as ex:
        raise RuntimeError(f"Could not segment audio: {ex}") from ex
