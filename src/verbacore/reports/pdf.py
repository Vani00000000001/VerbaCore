import time
from pathlib import Path
from typing import List, Dict, Any, Union

from xml.sax.saxutils import escape

from verbacore.utils.paths import get_font_search_paths, sanitize_display_filename

HAVE_REPORTLAB = False
PDF_FONT_NAME = 'Helvetica'
PDF_FONT_BOLD = 'Helvetica-Bold'

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    # Search and register available TrueType/OpenType Unicode fonts
    for font_path in get_font_search_paths():
        try:
            name = font_path.stem
            pdfmetrics.registerFont(TTFont(name, str(font_path)))
            PDF_FONT_NAME = name
            PDF_FONT_BOLD = name
            break
        except Exception:
            continue

    HAVE_REPORTLAB = True
except ImportError:
    pass


def render_pdf_transcript(
    filename: str,
    report_id: str,
    duration_sec: float,
    languages: Union[List[str], str],
    segments: List[Dict[str, Any]],
    output_pdf_path: Path
) -> None:
    if not HAVE_REPORTLAB:
        return
    doc = SimpleDocTemplate(
        str(output_pdf_path),
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'DocTitle', parent=styles['Heading1'],
        fontName=PDF_FONT_BOLD, fontSize=18, leading=22, textColor=colors.HexColor('#0F172A')
    )
    subtitle_style = ParagraphStyle(
        'DocSubtitle', parent=styles['Normal'],
        fontName=PDF_FONT_NAME, fontSize=9, leading=13, textColor=colors.HexColor('#475569')
    )
    meta_style = ParagraphStyle(
        'MetaStyle', parent=styles['Normal'],
        fontName=PDF_FONT_NAME, fontSize=9, leading=13, textColor=colors.HexColor('#1E293B')
    )
    ts_style = ParagraphStyle(
        'TSStyle', parent=styles['Normal'],
        fontName=PDF_FONT_BOLD, fontSize=8.5, leading=11, textColor=colors.HexColor('#0284C7')
    )
    speaker_style = ParagraphStyle(
        'SpkStyle', parent=styles['Normal'],
        fontName=PDF_FONT_BOLD, fontSize=9, leading=12, textColor=colors.HexColor('#7C3AED')
    )
    text_style = ParagraphStyle(
        'TextStyle', parent=styles['Normal'],
        fontName=PDF_FONT_NAME, fontSize=9.5, leading=14, textColor=colors.HexColor('#0F172A')
    )

    elements = [
        Paragraph("VerbaCore • Transcription Record", title_style),
        Paragraph("Chronological Speech Record with Precise Timestamps", subtitle_style),
        Spacer(1, 10),
        HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#0284C7'), spaceAfter=12)
    ]

    safe_filename = escape(sanitize_display_filename(filename))
    safe_report_id = escape(str(report_id)[:8])
    dur_str = f"{int(duration_sec // 60):02d}:{int(duration_sec % 60):02d}"
    lang_str = escape(", ".join(languages).upper() if isinstance(languages, list) else str(languages).upper())
    meta_data = [
        [Paragraph(f"<b>Document / Audio:</b> {safe_filename}", meta_style), Paragraph(f"<b>Reference ID:</b> {safe_report_id}", meta_style)],
        [Paragraph(f"<b>Duration:</b> {dur_str}", meta_style), Paragraph(f"<b>Language(s):</b> {lang_str}", meta_style)],
        [Paragraph(f"<b>Date:</b> {time.strftime('%Y-%m-%d %H:%M')}", meta_style), Paragraph("<b>Record Type:</b> Verbatim Transcript", meta_style)]
    ]
    meta_table = Table(meta_data, colWidths=[270, 270])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8FAFC')),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    elements.extend([meta_table, Spacer(1, 14)])

    elements.append(Paragraph(
        "Verbatim Transcript",
        ParagraphStyle('SecH', parent=styles['Heading2'], fontName=PDF_FONT_BOLD, fontSize=12, textColor=colors.HexColor('#0F172A'))
    ))
    elements.append(Spacer(1, 8))

    for seg in segments:
        start_m, start_s = divmod(seg['start'], 60)
        end_m, end_s = divmod(seg['end'], 60)
        ts_label = f"[{int(start_m):02d}:{start_s:05.2f} &rarr; {int(end_m):02d}:{end_s:05.2f}]"
        spk_label = escape(str(seg.get('speaker', 'Speaker 1')))
        seg_text = escape(str(seg.get('text', '')))

        seg_data = [
            [Paragraph(ts_label, ts_style), Paragraph(spk_label, speaker_style), Paragraph(seg_text, text_style)]
        ]
        t = Table(seg_data, colWidths=[100, 80, 360])
        t.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ('TOPPADDING', (0,0), (-1,-1), 4),
        ]))
        elements.append(t)

    elements.append(Spacer(1, 16))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#E2E8F0'), spaceAfter=6))
    elements.append(Paragraph("VerbaCore • Local Transcription Record", subtitle_style))
    doc.build(elements)


def render_pdf_executive_report(
    filename: str,
    report_id: str,
    duration_sec: float,
    languages: Union[List[str], str],
    segments: List[Dict[str, Any]],
    brain_data: Dict[str, Any],
    output_pdf_path: Path
) -> None:
    if not HAVE_REPORTLAB:
        return
    doc = SimpleDocTemplate(
        str(output_pdf_path),
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'DocTitle', parent=styles['Heading1'],
        fontName=PDF_FONT_BOLD, fontSize=18, leading=22, textColor=colors.HexColor('#0F172A')
    )
    subtitle_style = ParagraphStyle(
        'DocSubtitle', parent=styles['Normal'],
        fontName=PDF_FONT_NAME, fontSize=9, leading=13, textColor=colors.HexColor('#475569')
    )
    sec_style = ParagraphStyle(
        'SecHead', parent=styles['Heading2'],
        fontName=PDF_FONT_BOLD, fontSize=12, leading=16, textColor=colors.HexColor('#1E293B')
    )
    body_style = ParagraphStyle(
        'BodyText', parent=styles['Normal'],
        fontName=PDF_FONT_NAME, fontSize=9.5, leading=14, textColor=colors.HexColor('#334155')
    )
    meta_style = ParagraphStyle(
        'MetaStyle', parent=styles['Normal'],
        fontName=PDF_FONT_NAME, fontSize=9, leading=13, textColor=colors.HexColor('#1E293B')
    )
    speaker_style = ParagraphStyle(
        'SpkStyle', parent=styles['Normal'],
        fontName=PDF_FONT_BOLD, fontSize=9, leading=12, textColor=colors.HexColor('#7C3AED')
    )
    dialogue_style = ParagraphStyle(
        'CleanDial', parent=styles['Normal'],
        fontName=PDF_FONT_NAME, fontSize=9.5, leading=14, textColor=colors.HexColor('#0F172A')
    )

    elements = [
        Paragraph("VerbaCore • Executive Conversation Report", title_style),
        Paragraph("Executive Synthesis • Key Discussion Points • Dialogue Record", subtitle_style),
        Spacer(1, 10),
        HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#7C3AED'), spaceAfter=12)
    ]

    safe_filename = escape(sanitize_display_filename(filename))
    safe_report_id = escape(str(report_id)[:8])
    dur_str = f"{int(duration_sec // 60):02d}:{int(duration_sec % 60):02d}"
    lang_str = escape(", ".join(languages).upper() if isinstance(languages, list) else str(languages).upper())
    participant_status = escape(f"{brain_data.get('speaker_count', 1)} Participant(s)")

    meta_data = [
        [Paragraph(f"<b>Document / Audio:</b> {safe_filename}", meta_style), Paragraph(f"<b>Reference ID:</b> {safe_report_id}", meta_style)],
        [Paragraph(f"<b>Duration:</b> {dur_str}", meta_style), Paragraph(f"<b>Language(s):</b> {lang_str}", meta_style)],
        [Paragraph(f"<b>Date:</b> {time.strftime('%Y-%m-%d %H:%M')}", meta_style), Paragraph(f"<b>Participants:</b> {participant_status}", meta_style)]
    ]
    meta_table = Table(meta_data, colWidths=[270, 270])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8FAFC')),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    elements.extend([meta_table, Spacer(1, 14)])

    elements.append(Paragraph("1. Executive Summary", sec_style))
    elements.append(Spacer(1, 4))
    elements.append(Paragraph(escape(str(brain_data.get('executive_summary', ''))), body_style))
    elements.append(Spacer(1, 12))

    elements.append(Paragraph("2. Key Insights & Discussion Points", sec_style))
    elements.append(Spacer(1, 4))
    for t_item in brain_data.get('key_takeaways', []):
        elements.append(Paragraph(f"&bull; {escape(str(t_item))}", body_style))
        elements.append(Spacer(1, 2))
    elements.append(Spacer(1, 10))

    elements.append(Paragraph("3. Action Items & Decisions", sec_style))
    elements.append(Spacer(1, 4))
    for a_item in brain_data.get('action_items', []):
        elements.append(Paragraph(f"&bull; {escape(str(a_item))}", body_style))
        elements.append(Spacer(1, 2))
    elements.append(Spacer(1, 10))

    elements.append(Paragraph("4. Conversation Dialogue", sec_style))
    elements.append(Spacer(1, 6))
    for seg in segments:
        seg_data = [
            [Paragraph(escape(str(seg.get('speaker', 'Speaker 1'))), speaker_style), Paragraph(escape(str(seg.get('cleaned_text', seg['text']))), dialogue_style)]
        ]
        t = Table(seg_data, colWidths=[100, 440])
        t.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 3),
            ('TOPPADDING', (0,0), (-1,-1), 3),
        ]))
        elements.append(t)

    elements.append(Spacer(1, 16))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#E2E8F0'), spaceAfter=6))
    elements.append(Paragraph("Generated locally by VerbaCore • Executive Conversation Record", subtitle_style))
    doc.build(elements)
