import pytest
from pathlib import Path
from verbacore.reports.txt import render_txt_reports, render_srt
from verbacore.reports.pdf import render_pdf_transcript, render_pdf_executive_report, HAVE_REPORTLAB
from verbacore.reports.docx import render_docx_transcript, render_docx_executive_report, HAVE_DOCX


@pytest.fixture
def sample_data():
    segments = [
        {"start": 0.0, "end": 2.5, "speaker": "Speaker 1", "lang": "en", "text": "Hello world.", "cleaned_text": "Hello world."},
        {"start": 3.0, "end": 6.0, "speaker": "Speaker 2", "lang": "ta", "text": "Vanakkam, epdi irukinga?", "cleaned_text": "Vanakkam, epdi irukinga?"}
    ]
    brain = {
        "executive_summary": "The speakers greet each other and inquire about wellbeing.",
        "key_takeaways": ["Initial greeting exchanged.", "Bilingual English and Tamil conversation."],
        "action_items": ["Proceed with the planned agenda."]
    }
    return segments, brain


def test_txt_and_srt_reports(tmp_path, sample_data):
    segments, brain = sample_data
    txt_trans = tmp_path / "transcript.txt"
    txt_exec = tmp_path / "executive.txt"
    srt_file = tmp_path / "output.srt"

    render_txt_reports("test_meeting.wav", "rep12345", 6.0, ["en", "ta"], segments, brain, txt_trans, txt_exec)
    assert txt_trans.is_file()
    assert "Hello world." in txt_trans.read_text(encoding="utf-8")

    assert txt_exec.is_file()
    assert "executive summary" in txt_exec.read_text(encoding="utf-8").lower()

    render_srt(segments, srt_file)
    assert srt_file.is_file()
    assert "00:00:00,000 --> 00:00:02,500" in srt_file.read_text(encoding="utf-8")


def test_pdf_reports(tmp_path, sample_data):
    if not HAVE_REPORTLAB:
        pytest.skip("ReportLab not installed")
    segments, brain = sample_data
    pdf_trans = tmp_path / "transcript.pdf"
    pdf_exec = tmp_path / "executive.pdf"

    render_pdf_transcript("test_meeting.wav", "rep12345", 6.0, ["en", "ta"], segments, pdf_trans)
    assert pdf_trans.is_file()
    assert pdf_trans.stat().st_size > 500

    render_pdf_executive_report("test_meeting.wav", "rep12345", 6.0, ["en", "ta"], segments, brain, pdf_exec)
    assert pdf_exec.is_file()
    assert pdf_exec.stat().st_size > 500


def test_docx_reports(tmp_path, sample_data):
    if not HAVE_DOCX:
        pytest.skip("python-docx not installed")
    segments, brain = sample_data
    docx_trans = tmp_path / "transcript.docx"
    docx_exec = tmp_path / "executive.docx"

    render_docx_transcript("test_meeting.wav", "rep12345", 6.0, ["en", "ta"], segments, docx_trans)
    assert docx_trans.is_file()
    assert docx_trans.stat().st_size > 500

def test_pdf_reports_xml_characters_and_unsafe_filename(tmp_path, sample_data):
    if not HAVE_REPORTLAB:
        pytest.skip("ReportLab not installed")
    segments = [
        {"start": 0.0, "end": 2.0, "speaker": "Speaker <1>", "lang": "en", "text": "R&D <test> 5 > 3", "cleaned_text": "R&D <test> 5 > 3"}
    ]
    brain = {
        "executive_summary": "Discussion on A&B <script>alert(1)</script>.",
        "key_takeaways": ["Item 1 & Item 2"],
        "action_items": ["Check x < y"],
        "speaker_count": 1
    }
    pdf_trans = tmp_path / "xml_transcript.pdf"
    pdf_exec = tmp_path / "xml_exec.pdf"
    render_pdf_transcript("../../Q&A_<test>.wav", "rep12345", 2.0, ["en"], segments, pdf_trans)
    render_pdf_executive_report("../../Q&A_<test>.wav", "rep12345", 2.0, ["en"], segments, brain, pdf_exec)
    assert pdf_trans.is_file() and pdf_trans.stat().st_size > 500
    assert pdf_exec.is_file() and pdf_exec.stat().st_size > 500

