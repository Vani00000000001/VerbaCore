import re

PROMPT_HALLUCINATION_TRIGGERS = [
    "tamil and english conversation",
    "conversation with accurate spelling",
    "accurate spelling and grammar",
    "வணக்கம், எப்படி இருக்கீங்க",
    "clear, professional conversation",
    "accurate spelling, punctuation",
    "accurate grammar and spelling",
    "தெளிவான தமிழ் உரையாடல்",
    "சரியாகவும் எழுதுங்கள்",
    "स्पष्ट हिन्दी वार्तालाप",
    "सही व्याकरण का प्रयोग करें",
    "thank you for watching",
    "thanks for watching",
    "subscribe to",
    "subtitles by",
    "translated by",
]


def is_prompt_hallucination(text: str) -> bool:
    """Detects whether text is an echo of initial_prompt or a known silence hallucination."""
    if not text:
        return True
    lower = text.lower().strip().rstrip(".?!,")
    for trigger in PROMPT_HALLUCINATION_TRIGGERS:
        if trigger in lower or lower in trigger:
            return True
    return False


def clean_repetition_loops(text: str) -> str:
    """
    Stops and removes Whisper autoregressive hallucination loops.
    Collapses repeated n-grams and catches single-token dominance.
    """
    if not text or is_prompt_hallucination(text):
        return ""
    # Remove repeated adjacent words / tokens (e.g. "aga, aga, aga" -> "aga")
    text = re.sub(r"(\b\w+\b)(?:[\s,]+(?:\1|\W+)){2,}", r"\1", text, flags=re.IGNORECASE)
    # Check if a single token dominates > 55% of the entire output
    tokens = text.split()
    if len(tokens) > 4:
        most_common = max(set(tokens), key=tokens.count)
        if tokens.count(most_common) / len(tokens) > 0.55:
            return ""
    return text.strip()


def clean_clutter(text: str) -> str:
    """Filters out verbal fillers, stuttered words, and speech clutter."""
    if not text:
        return ""
    fillers = [r"\b(um+h*|uh+h*|er+m*|ah+h*)\b"]
    cleaned = text
    for pattern in fillers:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(\w+)\s+\1\b", r"\1", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = re.sub(r"\s+([,.?!])", r"\1", cleaned)
    return cleaned if cleaned else text
