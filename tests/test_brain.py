from verbacore.llm.brain import analyze_conversation_with_brain_llm
from verbacore.server import assign_speakers


def test_brain_llm_heuristic_fallback():
    segments = [
        {
            "start": 0.0,
            "end": 5.0,
            "speaker": "Speaker 1",
            "lang": "en",
            "text": "Testing the heuristic offline fallback.",
        },
        {
            "start": 7.5,
            "end": 12.0,
            "speaker": "Speaker 2",
            "lang": "ta",
            "text": "Idhu oru mukkiyamana kelvi.",
        },
        {
            "start": 14.5,
            "end": 20.0,
            "speaker": "Speaker 1",
            "lang": "en",
            "text": "Yes, we are evaluating multi-speaker turns.",
        },
        {
            "start": 22.0,
            "end": 25.0,
            "speaker": "Speaker 2",
            "lang": "ta",
            "text": "Sari, adhutha kattam enna?",
        },
    ]
    res = analyze_conversation_with_brain_llm(segments, duration_sec=25.0)
    assert isinstance(res, dict)
    assert "is_multi_speaker" in res
    assert "executive_summary" in res
    assert "key_takeaways" in res
    assert "action_items" in res
    assert len(res["executive_summary"]) > 10


def test_assign_speakers_single_and_multi():
    raw_segments = [
        {"start": 0.0, "end": 3.0, "lang": "en", "text": "Segment one."},
        {"start": 5.0, "end": 8.0, "lang": "ta", "text": "Segment two."},
    ]
    # Single speaker mode
    single_brain = {
        "is_multi_speaker": False,
        "segment_speakers": ["Speaker 1", "Speaker 1"],
    }
    assigned_single = assign_speakers(raw_segments, single_brain)
    assert len(assigned_single) == 2
    assert assigned_single[0]["speaker"] == "Speaker 1"
    assert assigned_single[1]["speaker"] == "Speaker 1"

    # Multi speaker with LLM speaker list
    multi_brain = {
        "is_multi_speaker": True,
        "segment_speakers": ["Speaker 1", "Speaker 2"],
    }
    assigned_multi = assign_speakers(raw_segments, multi_brain)
    assert assigned_multi[0]["speaker"] == "Speaker 1"
    assert assigned_multi[1]["speaker"] == "Speaker 2"
