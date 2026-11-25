import time
from pathlib import Path
from typing import List, Dict, Any, Union


def render_txt_reports(
    filename: str,
    report_id: str,
    duration_sec: float,
    languages: Union[List[str], str],
    segments: List[Dict[str, Any]],
    brain_data: Dict[str, Any],
    output_txt_path: Path,
    output_exec_txt_path: Path
) -> None:
    dur_str = f"{int(duration_sec // 60):02d}:{int(duration_sec % 60):02d}"
    lang_str = ", ".join(languages).upper() if isinstance(languages, list) else str(languages).upper()

    # 1. Verbatim Transcript TXT
    with open(output_txt_path, "w", encoding="utf-8") as f:
        f.write("=" * 70 + "\n")
        f.write("VERBACORE TRANSCRIPTION RECORD\n")
        f.write("Chronological Speech Record with Timestamps\n")
        f.write("=" * 70 + "\n\n")
        f.write(f"File Name     : {filename}\n")
        f.write(f"Reference ID  : {report_id[:8]}\n")
        f.write(f"Duration      : {dur_str}\n")
        f.write(f"Language(s)   : {lang_str}\n")
        f.write(f"Date          : {time.strftime('%Y-%m-%d %H:%M')}\n\n")
        f.write("-" * 70 + "\n")
        f.write("VERBATIM TRANSCRIPT\n")
        f.write("-" * 70 + "\n\n")
        for seg in segments:
            start_m, start_s = divmod(seg['start'], 60)
            end_m, end_s = divmod(seg['end'], 60)
            ts = f"[{int(start_m):02d}:{start_s:05.2f} -> {int(end_m):02d}:{end_s:05.2f}]"
            f.write(f"{ts}  {seg.get('speaker', 'Speaker 1')}: {seg['text']}\n")
        f.write("\n" + "=" * 70 + "\n")

    # 2. Executive Report TXT
    with open(output_exec_txt_path, "w", encoding="utf-8") as f:
        f.write("=" * 70 + "\n")
        f.write("VERBACORE EXECUTIVE CONVERSATION REPORT\n")
        f.write("Executive Synthesis • Key Discussion Points\n")
        f.write("=" * 70 + "\n\n")
        f.write(f"File Name     : {filename}\n")
        f.write(f"Reference ID  : {report_id[:8]}\n")
        f.write(f"Duration      : {dur_str}\n")
        f.write(f"Language(s)   : {lang_str}\n")
        f.write(f"Participants  : {brain_data.get('speaker_count', 1)}\n\n")
        f.write("1. EXECUTIVE SUMMARY\n" + "-" * 70 + "\n")
        f.write(f"{brain_data.get('executive_summary', '')}\n\n")
        f.write("2. KEY INSIGHTS & DISCUSSION POINTS\n" + "-" * 70 + "\n")
        for t_item in brain_data.get('key_takeaways', []):
            f.write(f"* {t_item}\n")
        f.write("\n3. ACTION ITEMS & DECISIONS\n" + "-" * 70 + "\n")
        for a_item in brain_data.get('action_items', []):
            f.write(f"* {a_item}\n")
        f.write("\n4. CONVERSATION DIALOGUE\n" + "-" * 70 + "\n\n")
        for seg in segments:
            f.write(f"{seg.get('speaker', 'Speaker 1')}: {seg.get('cleaned_text', seg['text'])}\n")
        f.write("\n" + "=" * 70 + "\n")


def render_srt(segments: List[Dict[str, Any]], output_srt_path: Path) -> None:
    """Generate SubRip (.srt) subtitle file."""
    try:
        import srt
        from datetime import timedelta

        subtitles = []
        for idx, seg in enumerate(segments, start=1):
            start = timedelta(seconds=seg['start'])
            end = timedelta(seconds=seg['end'])
            speaker = seg.get('speaker', '')
            prefix = f"{speaker}: " if speaker else ""
            content = f"{prefix}{seg['text']}"
            subtitles.append(srt.Subtitle(index=idx, start=start, end=end, content=content))

        output_srt_path.write_text(srt.compose(subtitles), encoding="utf-8")
    except ImportError:
        # Simple manual SRT generator
        lines = []
        for idx, seg in enumerate(segments, start=1):
            def fmt_ts(s: float) -> str:
                hrs = int(s // 3600)
                mins = int((s % 3600) // 60)
                secs = int(s % 60)
                millis = int((s - int(s)) * 1000)
                return f"{hrs:02d}:{mins:02d}:{secs:02d},{millis:03d}"

            speaker = seg.get('speaker', '')
            prefix = f"{speaker}: " if speaker else ""
            lines.append(f"{idx}\n{fmt_ts(seg['start'])} --> {fmt_ts(seg['end'])}\n{prefix}{seg['text']}\n")

        output_srt_path.write_text("\n".join(lines), encoding="utf-8")
