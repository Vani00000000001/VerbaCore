import time
from pathlib import Path
from typing import Any

from verbacore.utils.paths import sanitize_display_filename

try:
    import docx
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.shared import Pt, RGBColor

    HAVE_DOCX = True
except ImportError:
    HAVE_DOCX = False


def render_docx_transcript(
    filename: str,
    report_id: str,
    duration_sec: float,
    languages: list[str] | str,
    segments: list[dict[str, Any]],
    output_docx_path: Path,
) -> None:
    if not HAVE_DOCX:
        return
    doc = docx.Document()

    h = doc.add_heading(level=0)
    run = h.add_run("VerbaCore Transcription Record")
    run.font.name = "Calibri"
    run.font.color.rgb = RGBColor(15, 23, 42)

    p_sub = doc.add_paragraph("Chronological Speech Record with Precise Timestamps")
    p_sub.runs[0].font.color.rgb = RGBColor(71, 85, 105)
    p_sub.runs[0].font.size = Pt(10)

    dur_str = f"{int(duration_sec // 60):02d}:{int(duration_sec % 60):02d}"
    lang_str = (
        ", ".join(languages).upper() if isinstance(languages, list) else str(languages).upper()
    )
    table = doc.add_table(rows=3, cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.style = "Table Grid"

    safe_filename = sanitize_display_filename(filename)
    meta = [
        (f"File Name: {safe_filename}", f"Reference ID: {report_id[:8]}"),
        (f"Duration: {dur_str}", f"Language(s): {lang_str}"),
        (f"Date: {time.strftime('%Y-%m-%d %H:%M')}", "Format: Verbatim Transcript"),
    ]
    for row_idx, (c1, c2) in enumerate(meta):
        table.rows[row_idx].cells[0].text = c1
        table.rows[row_idx].cells[1].text = c2

    doc.add_paragraph()
    doc.add_heading("Verbatim Transcript", level=2)

    for seg in segments:
        start_m, start_s = divmod(seg["start"], 60)
        end_m, end_s = divmod(seg["end"], 60)
        ts_str = f"[{int(start_m):02d}:{start_s:05.2f} -> {int(end_m):02d}:{end_s:05.2f}]"

        p = doc.add_paragraph()
        run_ts = p.add_run(f"{ts_str}  ")
        run_ts.font.bold = True
        run_ts.font.color.rgb = RGBColor(2, 132, 199)
        run_ts.font.size = Pt(9.5)

        run_spk = p.add_run(f"{seg.get('speaker', 'Speaker 1')}: ")
        run_spk.font.bold = True
        run_spk.font.color.rgb = RGBColor(124, 58, 237)
        run_spk.font.size = Pt(9.5)

        run_txt = p.add_run(seg["text"])
        run_txt.font.size = Pt(10)

    doc.save(str(output_docx_path))


def render_docx_executive_report(
    filename: str,
    report_id: str,
    duration_sec: float,
    languages: list[str] | str,
    segments: list[dict[str, Any]],
    brain_data: dict[str, Any],
    output_docx_path: Path,
) -> None:
    if not HAVE_DOCX:
        return
    doc = docx.Document()

    h = doc.add_heading(level=0)
    run = h.add_run("VerbaCore Executive Conversation Report")
    run.font.name = "Calibri"
    run.font.color.rgb = RGBColor(15, 23, 42)

    p_sub = doc.add_paragraph("Executive Synthesis • Key Discussion Points • Dialogue Record")
    p_sub.runs[0].font.color.rgb = RGBColor(100, 116, 139)
    p_sub.runs[0].font.size = Pt(10)

    dur_str = f"{int(duration_sec // 60):02d}:{int(duration_sec % 60):02d}"
    lang_str = (
        ", ".join(languages).upper() if isinstance(languages, list) else str(languages).upper()
    )
    table = doc.add_table(rows=3, cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.style = "Table Grid"

    safe_filename = sanitize_display_filename(filename)
    meta = [
        (f"File Name: {safe_filename}", f"Reference ID: {report_id[:8]}"),
        (f"Duration: {dur_str}", f"Language(s): {lang_str}"),
        (
            f"Date: {time.strftime('%Y-%m-%d %H:%M')}",
            f"Participants: {brain_data.get('speaker_count', 1)}",
        ),
    ]
    for row_idx, (c1, c2) in enumerate(meta):
        table.rows[row_idx].cells[0].text = c1
        table.rows[row_idx].cells[1].text = c2

    doc.add_paragraph()
    doc.add_heading("1. Executive Summary", level=2)
    doc.add_paragraph(brain_data.get("executive_summary", "No summary generated."))

    doc.add_heading("2. Key Insights & Takeaways", level=2)
    for t_item in brain_data.get("key_takeaways", []):
        doc.add_paragraph(f"• {t_item}")

    doc.add_heading("3. Action Items", level=2)
    for a_item in brain_data.get("action_items", []):
        doc.add_paragraph(f"• {a_item}")

    doc.add_heading("4. Conversation Dialogue", level=2)
    for seg in segments:
        p = doc.add_paragraph()
        run_spk = p.add_run(f"{seg.get('speaker', 'Speaker 1')}: ")
        run_spk.font.bold = True
        run_spk.font.color.rgb = RGBColor(124, 58, 237)
        p.add_run(seg.get("cleaned_text", seg["text"]))

    doc.save(str(output_docx_path))
