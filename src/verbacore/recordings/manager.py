import json
import re
import shutil
import threading
import time
import uuid
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List

from verbacore.utils.paths import get_recordings_dir
from verbacore.utils.audio import convert_audio_to_mp3

RECORDING_RETENTION_DAYS = 30
_LOCKS_GUARD = threading.Lock()
_RECORDING_LOCKS: Dict[str, threading.Lock] = {}


def _get_recording_lock(recording_id: str) -> threading.Lock:
    with _LOCKS_GUARD:
        lock = _RECORDING_LOCKS.get(recording_id)
        if lock is None:
            lock = threading.Lock()
            _RECORDING_LOCKS[recording_id] = lock
        return lock


def get_recording_dir(recording_id: str) -> Path:
    if not re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", recording_id):
        raise ValueError("Invalid recording ID format")
    p = get_recordings_dir() / recording_id
    return p


def read_recording_manifest(recording_id: str) -> Dict[str, Any]:
    directory = get_recording_dir(recording_id)
    manifest_path = directory / "recording.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Recording {recording_id} not found")
    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_recording_manifest(recording_id: str, manifest: Dict[str, Any]) -> None:
    directory = get_recording_dir(recording_id)
    directory.mkdir(parents=True, exist_ok=True)
    temp_path = directory / "recording.json.tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    temp_path.replace(directory / "recording.json")


def create_recording(display_name: str, mime_type: str = "audio/webm") -> Tuple[str, Dict[str, Any]]:
    recording_id = str(uuid.uuid4())
    directory = get_recording_dir(recording_id)
    directory.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r'[\r\n"\\]', "_", Path(display_name or "recording").name)[:180]
    manifest = {
        "recording_id": recording_id,
        "display_name": safe_name,
        "mime_type": mime_type or "audio/webm",
        "created_at": time.time(),
        "finalized": False
    }
    save_recording_manifest(recording_id, manifest)
    return recording_id, manifest


def save_chunk(recording_id: str, chunk_index: int, data: bytes) -> Path:
    with _get_recording_lock(recording_id):
        directory = get_recording_dir(recording_id)
        if not directory.is_dir():
            raise FileNotFoundError("Recording session does not exist")
        chunk_path = directory / f"chunk-{chunk_index:06d}.part"
        temp_path = chunk_path.with_suffix(".tmp")
        temp_path.write_bytes(data)
        temp_path.replace(chunk_path)
        return chunk_path


def finalize_recording(recording_id: str, expected_chunks: Optional[int] = None) -> Tuple[Dict[str, Any], Path]:
    with _get_recording_lock(recording_id):
        directory = get_recording_dir(recording_id)
        manifest = read_recording_manifest(recording_id)
        source_path = directory / "source.webm"
        if source_path.is_file():
            return manifest, source_path

        chunk_paths = sorted(directory.glob("chunk-*.part"))
        if expected_chunks is not None and len(chunk_paths) != expected_chunks:
            raise RuntimeError(
                f"Recording incomplete: received {len(chunk_paths)} of {expected_chunks} chunks"
            )
        if not chunk_paths:
            raise FileNotFoundError("Recording has no saved audio chunks")

        expected_names = [f"chunk-{idx:06d}.part" for idx in range(len(chunk_paths))]
        if [p.name for p in chunk_paths] != expected_names:
            raise RuntimeError("Recording is incomplete: one or more audio chunks are missing")

        temp_path = directory / "source.webm.tmp"
        with open(temp_path, "wb") as out_f:
            for chunk_p in chunk_paths:
                with open(chunk_p, "rb") as in_f:
                    shutil.copyfileobj(in_f, out_f)
        temp_path.replace(source_path)

        for chunk_p in chunk_paths:
            chunk_p.unlink(missing_ok=True)

        manifest["finalized"] = True
        manifest["source_name"] = manifest["display_name"]
        manifest["finalized_at"] = time.time()
        save_recording_manifest(recording_id, manifest)
        return manifest, source_path


def create_mp3_for_recording(recording_id: str) -> Path:
    directory = get_recording_dir(recording_id)
    manifest = read_recording_manifest(recording_id)
    source_path = directory / "source.webm"
    if not source_path.is_file():
        raise FileNotFoundError("Recording source is not finalized")
    mp3_path = directory / "recording.mp3"
    if mp3_path.is_file():
        return mp3_path
    return convert_audio_to_mp3(source_path, mp3_path, title=manifest.get("display_name"))


def list_saved_recordings() -> List[Dict[str, Any]]:
    recordings_dir = get_recordings_dir()
    recordings = []
    expired_dirs: List[Path] = []
    now = time.time()
    retention_seconds = RECORDING_RETENTION_DAYS * 24 * 60 * 60
    for directory in list(recordings_dir.iterdir()):
        if not directory.is_dir():
            continue
        try:
            manifest = read_recording_manifest(directory.name)
            created_at = float(manifest.get("created_at", 0))
            if now - created_at > retention_seconds:
                expired_dirs.append(directory)
                continue
            recordings.append({
                "recording_id": manifest["recording_id"],
                "display_name": manifest.get("display_name", "Recording"),
                "created_at": created_at,
                "finalized": bool((directory / "source.webm").is_file()),
                "has_mp3": (directory / "recording.mp3").is_file()
            })
        except Exception:
            continue
    for expired_dir in expired_dirs:
        shutil.rmtree(expired_dir, ignore_errors=True)
    return sorted(recordings, key=lambda r: r["created_at"], reverse=True)


def delete_recording(recording_id: str) -> None:
    with _get_recording_lock(recording_id):
        directory = get_recording_dir(recording_id)
        if directory.is_dir():
            shutil.rmtree(directory)
