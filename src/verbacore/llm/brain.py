import json
import re
import urllib.request
import urllib.error
from typing import List, Dict, Any, Optional

from verbacore.config import AppConfig


def analyze_conversation_with_brain_llm(
    segments: List[Dict[str, Any]],
    duration_sec: float,
    config: Optional[AppConfig] = None
) -> Dict[str, Any]:
    """
    Calls the local Brain LLM (Ollama or llama-server) to perform:
    1. Single Speaker vs. Multi-Speaker Diarization with Bilingual Code-Switching awareness.
    2. Segment-by-segment speaker attribution.
    3. Executive Summary, Key Takeaways, and Action Items.
    """
    full_log = "\n".join(
        f"[{s['start']}s - {s['end']}s] ({s.get('lang', 'text')}): {s['text']}" for s in segments
    )

    sentences = [s['text'].strip() for s in segments if len(s['text'].strip()) > 3]
    default_overview = f"Audio recording analyzed over {int(duration_sec)} seconds."
    if sentences:
        default_overview += f" The discussion centers on: {sentences[0]}"
        if len(sentences) > 1:
            default_overview += f" with follow-up points including: {sentences[1]}"
    default_takeaways = [s for s in sentences[:3]] if sentences else ["Spoken dialogue recorded."]
    detected_langs = list(dict.fromkeys(s.get('lang', 'en').upper() for s in segments))

    prompt = f"""You are an elite linguistic conversation analyst and diarization AI for VerbaCore.
You excel at understanding bilingual code-switching (e.g. Tanglish, Hinglish) and distinguishing single-speaker monologues from multi-party conversations.

### CORE DIARIZATION LAWS:
1. THE BILINGUAL CODE-SWITCHING LAW:
   - In multilingual societies, a SINGLE person constantly mixes English and their native language.
   - A CHANGE IN LANGUAGE NEVER MEANS A CHANGE IN SPEAKER!
   - If one person expresses a continuous thought using two languages, classify as:
     "is_multi_speaker": false, "speaker_count": 1.
2. THE DIALOGUE RECIPROCITY LAW:
   - A multi-speaker conversation requires reciprocal interaction: Person A addresses Person B, and Person B gives an independent reply.
   - If there is no second person answering or reacting, it is a SINGLE SPEAKER.

### TASK INSTRUCTIONS:
Audio Duration: {int(duration_sec // 60)}m {int(duration_sec % 60)}s
Transcript Segments:
{full_log}

1. Analyze if this is a SINGLE SPEAKER or MULTI-SPEAKER.
2. For each segment, output its speaker label ("Speaker 1" for all if single-speaker).
3. List all identified languages.
4. Write a concise, professional 2-3 sentence executive summary explaining what was discussed or inquired.
5. Provide 2-3 key takeaways and explicit action items.

Output strictly valid JSON:
{{
  "is_multi_speaker": false,
  "speaker_count": 1,
  "segment_speakers": ["Speaker 1"],
  "languages": ["Tamil", "English"],
  "executive_summary": "The speaker greets the listener and inquires about the procedure for performing a task.",
  "key_takeaways": ["Single bilingual speaker initiated a query.", "The inquiry asks how to execute a specific task."],
  "action_items": ["Provide instructions on performing the requested task."]
}}"""

    model_name = config.brain_llm_model if config else "qwen2.5:1.5b"
    payload = {
        "model": model_name,
        "messages": [
            {
                "role": "system",
                "content": "You are a professional executive conversation analyst. Return ONLY strictly valid JSON. Never output placeholder dots or ellipses."
            },
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.1,
        "max_tokens": 450,
        "format": "json",
        "stream": False
    }

    endpoints = []
    if config and config.brain_llm_url:
        base = config.brain_llm_url.rstrip("/")
        endpoints.append(("Configured LLM", f"{base}/v1/chat/completions"))
    endpoints.extend([
        ("Ollama", "http://127.0.0.1:11434/v1/chat/completions"),
        ("llama-server", "http://127.0.0.1:8080/v1/chat/completions")
    ])

    # If neither endpoint is responding, attempt auto-launch via LLM manager
    try:
        from verbacore.llm.manager import ensure_brain_llm_active
        ensure_brain_llm_active(config)
    except Exception as e:
        print(f"[Brain LLM] LLM auto-start check: {e}")

    for name, endpoint in endpoints:
        try:
            req = urllib.request.Request(
                endpoint,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=30) as res:
                resp_data = json.loads(res.read().decode("utf-8"))
                raw_content = resp_data["choices"][0]["message"]["content"]
                match = re.search(r'\{.*\}', raw_content, re.DOTALL)
                if match:
                    data = json.loads(match.group(0))
                    summary = str(data.get("executive_summary", "")).strip()
                    if "..." in summary or len(summary) < 15:
                        summary = default_overview
                    data["executive_summary"] = summary

                    takeaways = data.get("key_takeaways", [])
                    cleaned_takeaways = [
                        t.strip() for t in takeaways
                        if isinstance(t, str) and "..." not in t and len(t.strip()) > 3
                    ]
                    data["key_takeaways"] = cleaned_takeaways or default_takeaways

                    actions = data.get("action_items", [])
                    cleaned_actions = [
                        a.strip() for a in actions
                        if isinstance(a, str) and "..." not in a and len(a.strip()) > 3
                    ]
                    data["action_items"] = cleaned_actions or ["No explicit action items recorded."]
                    return data
        except Exception:
            continue

    # Heuristic fallback if LLM is offline
    is_multi = (
        len(segments) >= 4 and
        duration_sec > 20 and
        any(segments[i]['start'] - segments[i-1]['end'] > 1.8 for i in range(1, len(segments)))
    )

    return {
        "is_multi_speaker": is_multi,
        "speaker_count": 2 if is_multi else 1,
        "languages": detected_langs or ["en"],
        "executive_summary": default_overview,
        "key_takeaways": default_takeaways,
        "action_items": ["Review dialogue highlights and action points."]
    }
