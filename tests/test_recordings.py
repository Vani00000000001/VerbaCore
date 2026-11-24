import pytest
from pathlib import Path
from verbacore.recordings.manager import (
    create_recording,
    save_chunk,
    finalize_recording,
    read_recording_manifest,
    save_recording_manifest,
    list_saved_recordings,
    delete_recording,
    get_recording_dir
)


def test_recording_lifecycle(tmp_path):
    rec_id, manifest = create_recording("test_audio.webm")
    assert rec_id
    assert manifest["display_name"] == "test_audio.webm"
    assert manifest["finalized"] is False

    # Save mock chunk
    chunk_file = save_chunk(rec_id, 0, b"\x00\x01\x02\x03")
    rec_dir = get_recording_dir(rec_id)
    assert chunk_file.is_file()

    # Finalize
    manifest, source_path = finalize_recording(rec_id)
    assert source_path.is_file()
    assert source_path.stat().st_size == 4

    # Read manifest
    updated = read_recording_manifest(rec_id)
    assert updated["finalized"] is True

    # Delete
    delete_recording(rec_id)
    assert not rec_dir.exists()


def test_invalid_recording_id():
    with pytest.raises(ValueError):
        get_recording_dir("../invalid_id")
