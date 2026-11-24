from verbacore.asr.guardrails import (
    is_prompt_hallucination,
    clean_repetition_loops,
    clean_clutter
)


def test_prompt_hallucination_detection():
    assert is_prompt_hallucination("thank you for watching")
    assert is_prompt_hallucination("Subtitles by")
    assert is_prompt_hallucination("வணக்கம், எப்படி இருக்கீங்க")
    assert not is_prompt_hallucination("We need to complete the deployment today.")


def test_repetition_loop_cleaner():
    # Repeated word sequence
    repeated = "The project status is good, good, good, good, good"
    cleaned = clean_repetition_loops(repeated)
    assert "good, good, good" not in cleaned

    # Normal text should not be erased
    normal = "The quick brown fox jumps over the lazy dog."
    assert clean_repetition_loops(normal) == normal


def test_clutter_cleaner():
    text = "So umm we should uh go ahead with this plan."
    cleaned = clean_clutter(text)
    assert "umm" not in cleaned
    assert "uh" not in cleaned
