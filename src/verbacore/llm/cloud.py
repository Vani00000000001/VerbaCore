import base64
import json
import os
import re
import urllib.request
import urllib.error
import uuid
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List

from verbacore.asr.guardrails import is_prompt_hallucination
from verbacore.llm.brain import analyze_conversation_with_brain_llm
from verbacore.config import AppConfig


def test_cloud_connection(provider: str, api_key: str) -> Tuple[bool, str]:
    """Test connectivity against Gemini or Groq."""
    if not api_key or not api_key.strip():
        return False, "API key cannot be empty."
    key = api_key.strip()
    try:
        if provider == "gemini":
            url = "https://generativelanguage.googleapis.com/v1beta/models"
            req = urllib.request.Request(
                url,
                headers={"x-goog-api-key": key, "User-Agent": "VerbaCore/0.2.0"}
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                if r.status == 200:
                    return True, "Google Gemini API connected successfully!"
        elif provider == "groq":
            url = "https://api.groq.com/openai/v1/models"
            req = urllib.request.Request(
                url,
                headers={"Authorization": f"Bearer {key}", "User-Agent": "VerbaCore/0.2.0"}
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                if r.status == 200:
                    return True, "Groq Cloud API connected successfully!"
        return False, f"Unknown cloud provider: {provider}"
    except urllib.error.HTTPError as he:
        return False, f"API Error (HTTP {he.code}): {he.reason}"
    except Exception as ex:
        return False, f"Connection failed: {ex}"


def transcribe_with_gemini(
    audio_path: Path,
    api_key: str,
    language_mode: str = "auto"
) -> Tuple[List[Dict[str, Any]], List[str], float, Dict[str, Any]]:
    """Multimodal transcription and diarization via Gemini Flash."""
    audio_bytes = audio_path.read_bytes()
    b64_audio = base64.b64encode(audio_bytes).decode("utf-8")
    suffix = audio_path.suffix.lower()
    mime_map = {
        '.mp3': 'audio/mp3', '.wav': 'audio/wav', '.webm': 'audio/webm',
        '.m4a': 'audio/m4a', '.ogg': 'audio/ogg', '.flac': 'audio/flac'
    }
    audio_mime = mime_map.get(suffix, 'audio/wav')

    prompt = (
        "Transcribe this conversation verbatim with precise timestamps and speaker tags.\n"
        "Return strictly valid JSON with this format:\n"
        "{\n"
        '  "is_multi_speaker": false,\n'
        '  "speaker_count": 1,\n'
        '  "languages": ["English"],\n'
        '  "executive_summary": "...",\n'
        '  "key_takeaways": ["..."],\n'
        '  "action_items": ["..."],\n'
        '  "segments": [\n'
        '    {"start": 0.0, "end": 2.5, "speaker": "Speaker 1", "text": "..."}\n'
        '  ]\n'
        "}"
    )

    models = ["gemini-2.5-flash", "gemini-1.5-flash"]
    last_error = None

    for model in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        payload = {
            "contents": [{
                "parts": [
                    {"inline_data": {"mime_type": audio_mime, "data": b64_audio}},
                    {"text": prompt}
                ]
            }],
            "generationConfig": {"temperature": 0.1, "response_mime_type": "application/json"}
        }

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json", "x-goog-api-key": api_key}
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                text = result["candidates"][0]["content"]["parts"][0]["text"]
                data = json.loads(text)

                raw_segments = []
                for s in data.get("segments", []):
                    txt = s.get("text", "").strip()
                    if txt:
                        raw_segments.append({
                            "start": round(float(s.get("start", 0.0)), 2),
                            "end": round(float(s.get("end", 0.0)), 2),
                            "speaker": s.get("speaker", "Speaker 1"),
                            "text": txt,
                            "cleaned_text": txt
                        })

                dur = max((s["end"] for s in raw_segments), default=10.0)
                brain_data = {
                    "is_multi_speaker": data.get("is_multi_speaker", False),
                    "speaker_count": data.get("speaker_count", 1),
                    "segment_speakers": [s.get("speaker", "Speaker 1") for s in raw_segments],
                    "languages": data.get("languages", ["English"]),
                    "executive_summary": data.get("executive_summary", "Summary not generated."),
                    "key_takeaways": data.get("key_takeaways", ["Dialogue captured."]),
                    "action_items": data.get("action_items", ["No explicit action items recorded."])
                }
                return raw_segments, brain_data["languages"], dur, brain_data
        except Exception as e:
            last_error = e
            continue

    raise RuntimeError(f"Gemini transcription failed: {last_error}")


def transcribe_with_groq(
    audio_path: Path,
    api_key: str,
    config: Optional[AppConfig] = None
) -> Tuple[List[Dict[str, Any]], List[str], float, Dict[str, Any]]:
    """Transcribe using Groq Whisper Large V3 Turbo."""
    audio_bytes = audio_path.read_bytes()
    boundary = f"----WebKitFormBoundary{uuid.uuid4().hex[:16]}"
    safe_name = audio_path.name
    suffix = audio_path.suffix.lower()
    mime_map = {
        '.mp3': 'audio/mpeg', '.wav': 'audio/wav', '.webm': 'audio/webm',
        '.m4a': 'audio/m4a', '.ogg': 'audio/ogg', '.flac': 'audio/flac'
    }
    content_mime = mime_map.get(suffix, 'audio/wav')

    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{safe_name}"\r\n'
        f"Content-Type: {content_mime}\r\n\r\n"
    ).encode("utf-8") + audio_bytes + (
        f"\r\n--{boundary}\r\n"
        f'Content-Disposition: form-data; name="model"\r\n\r\n'
        f"whisper-large-v3-turbo\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="response_format"\r\n\r\n'
        f"verbose_json\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="temperature"\r\n\r\n'
        f"0.0\r\n"
        f"--{boundary}--\r\n"
    ).encode("utf-8")

    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/audio/transcriptions",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": "VerbaCore/0.2.0"
        }
    )

    with urllib.request.urlopen(req, timeout=60) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        dur = float(res.get("duration", 10.0))
        lang = res.get("language", "en")

        raw_segments = []
        for s in res.get("segments", []):
            txt = s.get("text", "").strip()
            if not txt or is_prompt_hallucination(txt):
                continue
            raw_segments.append({
                "start": round(float(s.get("start", 0.0)), 2),
                "end": round(float(s.get("end", 0.0)), 2),
                "lang": lang,
                "text": txt,
                "cleaned_text": txt
            })

        brain_data = analyze_conversation_with_brain_llm(raw_segments, dur, config=config)
        return raw_segments, [lang.upper()], dur, brain_data
