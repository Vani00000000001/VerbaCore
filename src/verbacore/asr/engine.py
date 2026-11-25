from pathlib import Path
from typing import Any

try:
    from faster_whisper import WhisperModel
    from faster_whisper.audio import decode_audio
    from faster_whisper.vad import VadOptions, get_speech_timestamps

    HAVE_WHISPER = True
except ImportError:
    HAVE_WHISPER = False
    WhisperModel = None
    decode_audio = None
    get_speech_timestamps = None
    VadOptions = None

from verbacore.asr.guardrails import (
    clean_repetition_loops,
    is_prompt_hallucination,
)
from verbacore.utils.paths import get_models_dir

# Global model cache to avoid reallocating CT2 weights
_MODEL_CACHE: dict[str, Any] = {}


def get_whisper_model(
    model_size: str = "small",
    device: str = "cpu",
    compute_type: str = "int8",
    cpu_threads: int = 4,
) -> Any:
    """
    Get or load a faster-whisper model.
    Checks local model directories first; if not found, downloads from HuggingFace to get_models_dir().
    """
    if not HAVE_WHISPER:
        raise RuntimeError("faster-whisper dependencies are not installed.")

    cache_key = f"{model_size}:{device}:{compute_type}"
    if cache_key in _MODEL_CACHE:
        return _MODEL_CACHE[cache_key]

    models_dir = get_models_dir()

    # Check candidates for local offline weights
    candidate_dirs = [
        models_dir / f"faster-whisper-{model_size}",
        models_dir / model_size,
        Path.home() / ".cache" / "huggingface" / "hub",
    ]

    local_path = None
    for cand in candidate_dirs:
        if cand.is_dir() and (
            (cand / "model.bin").is_file() or (cand / "model.safetensors").is_file()
        ):
            local_path = str(cand)
            break

    model_target = local_path if local_path else model_size
    download_root = str(models_dir)

    model = WhisperModel(
        model_target,
        device=device,
        compute_type=compute_type,
        cpu_threads=cpu_threads,
        download_root=download_root,
    )
    _MODEL_CACHE[cache_key] = model
    return model


def transcribe_audio_turns(
    audio_path: Path, model_size: str = "small", language_mode: str = "auto"
) -> tuple[list[dict[str, Any]], list[str], float]:
    """
    Turn-based multilingual ASR engine with streaming chunk segmentation,
    greedy decoding, and dynamic sentence-level language switching.
    """
    if not HAVE_WHISPER:
        raise RuntimeError("faster-whisper is not available.")

    audio = decode_audio(str(audio_path))
    duration_s = len(audio) / 16000.0
    model = get_whisper_model(model_size)

    # 1. Global language detection anchor
    g_lang, _, g_all = model.detect_language(audio)
    top_langs_map = dict(g_all[:10])

    allowed_langs: set[str] | None = None
    if language_mode == "code_switch_ta_en":
        allowed_langs = {"ta", "en"}
    elif language_mode == "code_switch_hi_en":
        allowed_langs = {"hi", "en"}
    elif language_mode == "auto":
        if g_lang == "ta" or (
            top_langs_map.get("ta", 0.0) > 0.15 and top_langs_map.get("hi", 0.0) < 0.35
        ):
            allowed_langs = {"ta", "en"}
        elif g_lang == "hi" or (
            top_langs_map.get("hi", 0.0) > 0.25 and top_langs_map.get("ta", 0.0) < 0.20
        ):
            allowed_langs = {"hi", "en"}
        elif g_lang == "en" and top_langs_map.get("ta", 0.0) > 0.08:
            allowed_langs = {"ta", "en"}

    # 2. Turn-level chunk segmentation (>500ms pause)
    turn_vad = VadOptions(min_silence_duration_ms=500, speech_pad_ms=200)
    turns = get_speech_timestamps(audio, turn_vad)
    if not turns:
        turns = [{"start": 0, "end": len(audio)}]

    # 3. Sentence-level segmentation (>250ms pause)
    sentence_vad = VadOptions(min_silence_duration_ms=250, speech_pad_ms=100)

    vocab_prompts = {
        "ta": "வணக்கம், AI, தொழில்நுட்பம்.",
        "hi": "नमस्ते, AI, टेक्नोलॉजी.",
        "en": "Hello, Artificial Intelligence, technology.",
    }

    raw_segments: list[dict[str, Any]] = []
    detected_languages: set[str] = set()

    def pick_sentence_language(sent_audio) -> str:
        if language_mode not in ("auto", "code_switch_ta_en", "code_switch_hi_en"):
            return language_mode

        _, _, all_probs = model.detect_language(sent_audio)
        prob_dict = dict(all_probs)

        if allowed_langs:
            ranked = sorted(allowed_langs, key=lambda lang: prob_dict.get(lang, 0.0), reverse=True)
            best = ranked[0]
            if prob_dict.get(best, 0.0) < 0.05 and g_lang in allowed_langs:
                best = g_lang
            return best

        best_lang, best_prob = all_probs[0]
        if best_prob < 0.60 or best_lang in (
            "tl",
            "cy",
            "haw",
            "jw",
            "sn",
            "su",
            "mr",
            "ur",
        ):
            best_lang = g_lang
        return best_lang

    for turn in turns:
        turn_audio = audio[turn["start"] : turn["end"]]
        if len(turn_audio) < 2400:  # Skip turns < 0.15s
            continue

        sentences = get_speech_timestamps(turn_audio, sentence_vad)
        if not sentences:
            sentences = [{"start": 0, "end": len(turn_audio)}]

        for sent in sentences:
            sent_audio = turn_audio[sent["start"] : sent["end"]]
            if len(sent_audio) < 1600:  # Skip units < 0.1s
                continue

            offset_s = (turn["start"] + sent["start"]) / 16000.0
            best_lang = pick_sentence_language(sent_audio)
            detected_languages.add(best_lang)

            segs, _ = model.transcribe(
                sent_audio,
                language=best_lang,
                initial_prompt=vocab_prompts.get(best_lang),
                beam_size=1,
                temperature=0.0,
                repetition_penalty=1.20,
                no_repeat_ngram_size=3,
                condition_on_previous_text=False,
                vad_filter=False,
            )

            for s in segs:
                if getattr(s, "no_speech_prob", 0.0) > 0.60:
                    continue
                cleaned_text = clean_repetition_loops(s.text)
                if cleaned_text and not is_prompt_hallucination(cleaned_text):
                    raw_segments.append(
                        {
                            "start": round(offset_s + s.start, 2),
                            "end": round(offset_s + s.end, 2),
                            "lang": best_lang,
                            "text": cleaned_text,
                        }
                    )

    final_langs = detect_verified_languages(raw_segments, detected_languages)
    return raw_segments, final_langs, duration_s


def detect_verified_languages(
    raw_segments: list[dict[str, Any]], detected_languages: set[str]
) -> list[str]:
    """Validate detected languages against Unicode character scripts in transcribed text."""
    verified_langs: set[str] = set()
    for s in raw_segments:
        t = s.get("text", "")
        if any("\u0b80" <= c <= "\u0bff" for c in t):
            verified_langs.add("TAMIL")
        if any("a" <= c.lower() <= "z" or "\u00c0" <= c <= "\u024f" for c in t):
            verified_langs.add("ENGLISH")
        if any("\u0900" <= c <= "\u097f" for c in t):
            verified_langs.add("HINDI")

    return (
        sorted(verified_langs)
        if verified_langs
        else sorted(lang.upper() for lang in detected_languages)
    )
