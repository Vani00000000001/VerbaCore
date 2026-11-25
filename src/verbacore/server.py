import json
import mimetypes
import re
import uuid
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from verbacore.asr.engine import HAVE_WHISPER, transcribe_audio_turns
from verbacore.asr.guardrails import clean_clutter
from verbacore.config import load_config
from verbacore.llm.brain import analyze_conversation_with_brain_llm
from verbacore.llm.cloud import (
    test_cloud_connection,
    transcribe_with_gemini,
    transcribe_with_groq,
)
from verbacore.recordings.manager import (
    RECORDING_RETENTION_DAYS,
    create_mp3_for_recording,
    create_recording,
    delete_recording,
    finalize_recording,
    get_recording_dir,
    list_saved_recordings,
    read_recording_manifest,
    save_chunk,
    save_recording_manifest,
)
from verbacore.reports.docx import (
    HAVE_DOCX,
    render_docx_executive_report,
    render_docx_transcript,
)
from verbacore.reports.pdf import (
    HAVE_REPORTLAB,
    render_pdf_executive_report,
    render_pdf_transcript,
)
from verbacore.reports.txt import render_srt, render_txt_reports
from verbacore.utils.paths import (
    get_data_dir,
    get_models_dir,
    get_project_root,
    get_reports_dir,
)

config = load_config()
app = FastAPI(title="VerbaCore", version="0.2.0")

# CORS Configuration: restricted to same-origin localhost only. This is a local-first
# desktop application; arbitrary cross-origin sites must not be able to reach the local
# API, especially not with credentials, as that exposes cloud keys, recordings, and
# transcriptions to any site the user visits.
_host = config.host
_port = config.port
_ALLOWED_ORIGINS = {
    f"http://127.0.0.1:{_port}",
    f"http://localhost:{_port}",
}
if _host not in ("127.0.0.1", "localhost", "0.0.0.0"):
    _ALLOWED_ORIGINS.add(f"http://{_host}:{_port}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(_ALLOWED_ORIGINS),
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Accept", "Origin"],
)

# Upload safety limits
MAX_CHUNK_BYTES = 64 * 1024 * 1024  # 64 MB per recording chunk

# Resolve static directory (package root or project root)
static_dir = Path(__file__).resolve().parent.parent.parent / "static"
if not static_dir.is_dir():
    static_dir = get_project_root() / "static"

if static_dir.is_dir():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


def _recording_bytes_used(recording_id: str) -> int:
    """Return total bytes already stored for a recording (chunks + source + mp3)."""
    directory = get_recording_dir(recording_id)
    if not directory.is_dir():
        return 0
    total = 0
    for p in directory.rglob("*"):
        if p.is_file():
            try:
                total += p.stat().st_size
            except OSError:
                pass
    return total


def assign_speakers(
    raw_segments: list[dict[str, Any]], brain_data: dict[str, Any]
) -> list[dict[str, Any]]:
    if not raw_segments:
        return []
    is_multi = brain_data.get("is_multi_speaker", False)
    llm_speakers = brain_data.get("segment_speakers", [])
    assigned = []
    current_speaker = 1
    last_end = 0.0

    for i, seg in enumerate(raw_segments):
        start = seg.get("start", 0.0)
        end = seg.get("end", 0.0)
        raw_text = seg.get("text", "").strip()
        cleaned = clean_clutter(raw_text)

        if not is_multi:
            spk_label = "Speaker 1"
        elif isinstance(seg.get("speaker"), str) and re.fullmatch(r"Speaker \d+", seg["speaker"]):
            spk_label = seg["speaker"]
        elif (
            i < len(llm_speakers)
            and isinstance(llm_speakers[i], str)
            and re.fullmatch(r"Speaker \d+", llm_speakers[i])
        ):
            spk_label = llm_speakers[i]
        else:
            pause = start - last_end
            if i > 0 and pause >= 1.5:
                current_speaker = 2 if current_speaker == 1 else 1
            spk_label = f"Speaker {current_speaker}"

        assigned.append(
            {
                "start": start,
                "end": end,
                "speaker": spk_label,
                "lang": seg.get("lang", "en"),
                "text": raw_text,
                "cleaned_text": cleaned,
            }
        )
        last_end = end

    return assigned


@app.get("/", response_class=HTMLResponse)
@app.get("/index.html", response_class=HTMLResponse)
async def serve_index():
    index_file = static_dir / "index.html"
    if not index_file.is_file():
        raise HTTPException(status_code=404, detail="Frontend assets not found")
    return HTMLResponse(content=index_file.read_text(encoding="utf-8"))


@app.get("/api/health")
async def health_check():
    return {
        "status": "ok",
        "version": "0.2.0",
        "have_whisper": HAVE_WHISPER,
        "have_reportlab": HAVE_REPORTLAB,
        "have_docx": HAVE_DOCX,
    }


@app.get("/api/models")
async def get_models():
    models_dir = get_models_dir()
    labels = {
        "medium": "faster-whisper Medium (Pro Studio • 769M)",
        "small": "faster-whisper Small (High Accuracy • 244M)",
        "base": "faster-whisper Base (Fast • 74M)",
        "tiny": "faster-whisper Tiny (Ultra Fast)",
    }
    local_list = []
    for m_id, label in labels.items():
        candidate = models_dir / f"faster-whisper-{m_id}"
        installed = (candidate / "model.bin").is_file() or (
            candidate / "model.safetensors"
        ).is_file()
        local_list.append({"id": m_id, "label": label, "installed": installed})

    brain_status = {"online": False, "provider": "none"}
    try:
        from verbacore.llm.manager import check_llama_server_status, check_ollama_status

        ollama = check_ollama_status()
        llama = check_llama_server_status()
        if ollama["running"]:
            brain_status = {
                "online": True,
                "provider": "ollama",
                "url": ollama["url"],
                "models": ollama["models"],
            }
        elif llama["running"]:
            brain_status = {
                "online": True,
                "provider": "llama-server",
                "url": llama["url"],
                "model": llama["loaded_model"],
            }
    except Exception:
        pass

    return {
        "local": local_list,
        "cloud": [
            {"id": "cloud_gemini", "label": "Google Gemini Flash (Multimodal Audio)"},
            {"id": "cloud_groq", "label": "Groq Whisper Large V3 (Cloud LPU Fast)"},
        ],
        "brain": brain_status,
    }


@app.get("/api/recordings")
async def get_recordings():
    return {
        "recordings": list_saved_recordings(),
        "retention_days": RECORDING_RETENTION_DAYS,
    }


@app.get("/api/recordings/{recording_id}/mp3")
async def get_recording_mp3(recording_id: str):
    try:
        mp3_path = create_mp3_for_recording(recording_id)
        manifest = read_recording_manifest(recording_id)
        display_name = manifest.get("display_name", "recording")
        filename = re.sub(r'[\r\n"\\]', "_", Path(display_name).stem) + ".mp3"
        return FileResponse(str(mp3_path), media_type="audio/mpeg", filename=filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        print(f"[VerbaCore] recording mp3 error: {e!r}")
        raise HTTPException(status_code=500, detail="Could not prepare recording")


@app.delete("/api/recordings/{recording_id}")
async def remove_recording(recording_id: str):
    try:
        delete_recording(recording_id)
        return {"status": "ok"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/recordings/start")
async def start_recording(request: Request):
    data = await request.json()
    name = data.get("name", "Recording")
    mime_type = data.get("mime_type", "audio/webm")
    rec_id, manifest = create_recording(name, mime_type)
    return {"status": "ok", "recording_id": rec_id, "manifest": manifest}


@app.put("/api/recordings/{recording_id}/chunks/{chunk_index}")
async def upload_recording_chunk(recording_id: str, chunk_index: int, request: Request):
    body = await request.body()
    if not body:
        raise HTTPException(status_code=400, detail="Empty chunk data")
    if len(body) > MAX_CHUNK_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Chunk exceeds maximum size of {MAX_CHUNK_BYTES // (1024 * 1024)}MB",
        )
    used = _recording_bytes_used(recording_id)
    if used + len(body) > config.max_recording_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Recording exceeds maximum size of {config.max_recording_bytes // (1024 * 1024)}MB",
        )
    try:
        save_chunk(recording_id, chunk_index, body)
        return {"status": "ok", "chunk": chunk_index}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/recordings/{recording_id}/finalize")
async def finalize_recording_session(recording_id: str, request: Request):
    raw_body = await request.body()
    try:
        data = json.loads(raw_body) if raw_body else {}
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON request body")
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Request body must be a JSON object")
    expected_chunks = data.get("expected_chunks")
    try:
        manifest, source_path = finalize_recording(recording_id, expected_chunks)
        return {
            "status": "ok",
            "recording_id": manifest["recording_id"],
            "name": manifest["display_name"],
            "size": source_path.stat().st_size,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/cloud-config")
async def get_cloud_settings():
    cfg = load_config()
    return {
        "has_gemini": bool(cfg.gemini_api_key),
        "has_groq": bool(cfg.groq_api_key),
        "auto_fallback": cfg.auto_fallback,
        "preferred_cloud": cfg.preferred_cloud,
    }


@app.post("/api/cloud-config")
async def update_cloud_settings(request: Request):
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON request body")
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Request body must be a JSON object")
    config_file = get_data_dir() / "cloud_config.json"
    existing = {}
    if config_file.is_file():
        try:
            existing = json.loads(config_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    gem_key = data.get("gemini_api_key")
    if isinstance(gem_key, str) and not gem_key.startswith("***"):
        existing["gemini_api_key"] = gem_key.strip()
    groq_key = data.get("groq_api_key")
    if isinstance(groq_key, str) and not groq_key.startswith("***"):
        existing["groq_api_key"] = groq_key.strip()
    if "auto_fallback" in data:
        existing["auto_fallback"] = bool(data["auto_fallback"])
    if "preferred_cloud" in data and data["preferred_cloud"] in ("gemini", "groq"):
        existing["preferred_cloud"] = str(data["preferred_cloud"])

    config_file.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    return {"status": "ok", "message": "Cloud settings saved successfully"}


@app.post("/api/test-cloud")
async def test_cloud(request: Request):
    data = await request.json()
    provider = data.get("provider", "gemini")
    key = data.get("key", "").strip()
    if not key or key.startswith("***"):
        cfg = load_config()
        key = (cfg.gemini_api_key if provider == "gemini" else cfg.groq_api_key) or ""
    success, msg = test_cloud_connection(provider, key)
    return {"success": success, "message": msg}


@app.post("/api/transcribe")
async def transcribe(
    audio: UploadFile | None = File(None),
    model: str = Form("small"),
    language_mode: str = Form("auto"),
    recording_id: str | None = Form(None),
):
    if not audio and not recording_id:
        raise HTTPException(status_code=400, detail="No audio file or recording ID provided")

    report_id = str(uuid.uuid4())
    reports_dir = get_reports_dir()

    if recording_id:
        try:
            rec_dir = get_recording_dir(recording_id)
            source_path = rec_dir / "source.webm"
            manifest = read_recording_manifest(recording_id)
            safe_name = manifest.get("display_name", "recording.webm")
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))
    else:
        assert audio is not None
        safe_name = Path(audio.filename or "recording.wav").name
        rec_id, manifest = create_recording(safe_name, audio.content_type or "audio/wav")
        recording_id = rec_id
        source_path = get_recording_dir(rec_id) / "source.webm"

        # Enforce max upload size limit
        bytes_read = 0
        chunk_size = 1024 * 1024
        try:
            with open(source_path, "wb") as f:
                while chunk := await audio.read(chunk_size):
                    bytes_read += len(chunk)
                    if bytes_read > config.max_upload_bytes:
                        f.close()
                        source_path.unlink(missing_ok=True)
                        delete_recording(rec_id)
                        raise HTTPException(
                            status_code=413,
                            detail=f"Uploaded file exceeds maximum limit of {config.max_upload_bytes // (1024 * 1024)}MB",
                        )
                    f.write(chunk)
        except HTTPException:
            raise
        except Exception as e:
            source_path.unlink(missing_ok=True)
            delete_recording(rec_id)
            raise HTTPException(status_code=500, detail=f"Failed to save upload: {e}")

        manifest["finalized"] = True
        save_recording_manifest(rec_id, manifest)

    clean_stem = Path(safe_name).stem.replace(" ", "_")
    fallback_used = None
    engine_label = f"Local Whisper ({model})"
    cloud_provider_used = None
    cfg = load_config()

    try:
        if model == "cloud_gemini":
            engine_label = "Google Gemini Flash (Cloud)"
            cloud_provider_used = "gemini"
            if not cfg.gemini_api_key:
                raise ValueError("Gemini API key is not configured.")
            raw_segments, final_languages, dur, brain_data = transcribe_with_gemini(
                source_path, cfg.gemini_api_key, language_mode
            )
            segments_with_speakers = assign_speakers(raw_segments, brain_data)
        elif model == "cloud_groq":
            engine_label = "Groq Whisper Large V3 (Cloud)"
            cloud_provider_used = "groq"
            if not cfg.groq_api_key:
                raise ValueError("Groq API key is not configured.")
            raw_segments, final_languages, dur, brain_data = transcribe_with_groq(
                source_path, cfg.groq_api_key, config=cfg
            )
            segments_with_speakers = assign_speakers(raw_segments, brain_data)
        else:
            try:
                raw_segments, detected_langs, dur = transcribe_audio_turns(
                    source_path, model_size=model, language_mode=language_mode
                )
                brain_data = analyze_conversation_with_brain_llm(raw_segments, dur, config=cfg)
                final_languages = brain_data.get("languages", []) or detected_langs
                segments_with_speakers = assign_speakers(raw_segments, brain_data)
            except Exception:
                if cfg.auto_fallback and cfg.gemini_api_key:
                    fallback_used = "Google Gemini Flash (Cloud Fallback)"
                    engine_label = fallback_used
                    cloud_provider_used = "gemini"
                    raw_segments, final_languages, dur, brain_data = transcribe_with_gemini(
                        source_path, cfg.gemini_api_key, language_mode
                    )
                    segments_with_speakers = assign_speakers(raw_segments, brain_data)
                elif cfg.auto_fallback and cfg.groq_api_key:
                    fallback_used = "Groq Whisper Large V3 (Cloud Fallback)"
                    engine_label = fallback_used
                    cloud_provider_used = "groq"
                    raw_segments, final_languages, dur, brain_data = transcribe_with_groq(
                        source_path, cfg.groq_api_key, config=cfg
                    )
                    segments_with_speakers = assign_speakers(raw_segments, brain_data)
                else:
                    raise

        dur_m, dur_s = divmod(dur, 60)
        dur_str = f"{int(dur_m):02d}:{int(dur_s):02d}"
        total_words = sum(len(s["text"].split()) for s in raw_segments)

        # 1. Render PDF Reports
        pdf_transcript_name = f"{clean_stem}_{report_id[:8]}_transcript.pdf"
        render_pdf_transcript(
            safe_name,
            report_id,
            dur,
            final_languages,
            segments_with_speakers,
            reports_dir / pdf_transcript_name,
        )

        pdf_exec_name = f"{clean_stem}_{report_id[:8]}_executive_report.pdf"
        render_pdf_executive_report(
            safe_name,
            report_id,
            dur,
            final_languages,
            segments_with_speakers,
            brain_data,
            reports_dir / pdf_exec_name,
        )

        # 2. Render DOCX Reports
        docx_transcript_name = f"{clean_stem}_{report_id[:8]}_transcript.docx"
        render_docx_transcript(
            safe_name,
            report_id,
            dur,
            final_languages,
            segments_with_speakers,
            reports_dir / docx_transcript_name,
        )

        docx_exec_name = f"{clean_stem}_{report_id[:8]}_executive_report.docx"
        render_docx_executive_report(
            safe_name,
            report_id,
            dur,
            final_languages,
            segments_with_speakers,
            brain_data,
            reports_dir / docx_exec_name,
        )

        # 3. Render TXT & SRT Reports
        txt_transcript_name = f"{clean_stem}_{report_id[:8]}_transcript.txt"
        txt_exec_name = f"{clean_stem}_{report_id[:8]}_executive_report.txt"
        render_txt_reports(
            safe_name,
            report_id,
            dur,
            final_languages,
            segments_with_speakers,
            brain_data,
            reports_dir / txt_transcript_name,
            reports_dir / txt_exec_name,
        )

        srt_name = f"{clean_stem}_{report_id[:8]}.srt"
        render_srt(segments_with_speakers, reports_dir / srt_name)

        unavailable_exports = []
        if not HAVE_REPORTLAB:
            unavailable_exports.append("PDF")
        if not HAVE_DOCX:
            unavailable_exports.append("DOCX")

        is_cloud = bool(
            fallback_used
            or (cloud_provider_used and cloud_provider_used != "local")
            or "cloud" in engine_label.lower()
        )
        processing_loc = "cloud" if is_cloud else "local"

        files_map = {
            "pdf_transcript": pdf_transcript_name if HAVE_REPORTLAB else None,
            "pdf_executive": pdf_exec_name if HAVE_REPORTLAB else None,
            "docx_transcript": docx_transcript_name if HAVE_DOCX else None,
            "docx_executive": docx_exec_name if HAVE_DOCX else None,
            "txt_transcript": txt_transcript_name,
            "txt_executive": txt_exec_name,
            "srt": srt_name,
        }

        return {
            "status": "success",
            "report_id": report_id,
            "filename": safe_name,
            "duration_seconds": dur,
            "duration_formatted": dur_str,
            "languages": final_languages,
            "word_count": total_words,
            "segments": segments_with_speakers,
            "brain": brain_data,
            "fallback_used": fallback_used,
            "recording_id": recording_id,
            "engine": engine_label,
            "engine_used": engine_label,
            "processing_location": processing_loc,
            "cloud_provider": cloud_provider_used,
            "unavailable_exports": unavailable_exports,
            "pdf_transcript": files_map["pdf_transcript"],
            "pdf_executive": files_map["pdf_executive"],
            "docx_transcript": files_map["docx_transcript"],
            "docx_executive": files_map["docx_executive"],
            "txt_transcript": files_map["txt_transcript"],
            "txt_executive": files_map["txt_executive"],
            "srt": files_map["srt"],
            "files": files_map,
        }
    except Exception as e:
        print(f"[VerbaCore] transcribe error: {e!r}")
        raise HTTPException(status_code=500, detail="Transcription failed")


@app.get("/api/reports/{filename:path}")
async def get_report_file(filename: str):
    # Reject directory traversal attempts and path separators
    if Path(filename).name != filename or ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid report filename")

    reports_dir = get_reports_dir().resolve()
    file_path = (reports_dir / filename).resolve()

    if not file_path.is_file() or file_path.parent != reports_dir:
        raise HTTPException(status_code=404, detail="Report file not found")

    media_type, _ = mimetypes.guess_type(str(file_path))
    return FileResponse(
        str(file_path),
        media_type=media_type or "application/octet-stream",
        filename=filename,
    )


def main():
    cfg = load_config()
    print("=" * 70)
    print("  VERBACORE [Portable Launch Edition]")
    print(f"  Live Server:    http://{cfg.host}:{cfg.port}")
    print(f"  Data Directory: {get_data_dir()}")
    try:
        from verbacore.llm.manager import check_llama_server_status, check_ollama_status

        ollama = check_ollama_status()
        llama = check_llama_server_status()
        if ollama["running"]:
            print("  Brain LLM:      Ollama active on port 11434")
        elif llama["running"]:
            print(f"  Brain LLM:      llama-server active on port 8080 ({llama['loaded_model']})")
        else:
            print("  Brain LLM:      Standby (will auto-launch llama.cpp if requested)")
    except Exception:
        pass
    print("=" * 70)
    uvicorn.run(app, host=cfg.host, port=cfg.port, log_level="info")


if __name__ == "__main__":
    main()
