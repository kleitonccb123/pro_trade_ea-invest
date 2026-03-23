"""
Education Service - Business logic for quiz scoring, certificate generation,
and video URL extraction (YouTube / Vimeo embed support).

Author: Crypto Trade Hub
"""

from __future__ import annotations

import hashlib
import re
import secrets
from datetime import datetime
from io import BytesIO
from typing import Dict, List, Optional, Tuple


def extract_video_embed(
    video_url: Optional[str],
    provider: Optional[str] = None,
) -> Dict[str, str]:
    """
    Parses a video URL and returns embed information.

    Supports:
    - YouTube (youtube.com/watch?v=..., youtu.be/..., youtube.com/embed/...)
    - Vimeo (vimeo.com/..., player.vimeo.com/video/...)
    - Direct video URL (mp4, webm, etc.)

    Returns a dict with keys:
        embed_url, provider, video_id, original_url
    """
    original = video_url or ""

    if not original:
        return {
            "embed_url": "",
            "provider": "direct",
            "video_id": "",
            "original_url": original,
        }

    # Already an embed URL — return as-is with detected provider
    if "youtube.com/embed/" in original:
        m = re.search(r"/embed/([a-zA-Z0-9_-]{11})", original)
        vid_id = m.group(1) if m else ""
        return {
            "embed_url": original,
            "provider": "youtube",
            "video_id": vid_id,
            "original_url": original,
        }
    if "player.vimeo.com/video/" in original:
        m = re.search(r"/video/(\d+)", original)
        vid_id = m.group(1) if m else ""
        return {
            "embed_url": original,
            "provider": "vimeo",
            "video_id": vid_id,
            "original_url": original,
        }

    # YouTube patterns (watch?v=, youtu.be/, shorts/)
    yt_pattern = r"(?:youtube\.com/(?:watch\?v=|shorts/)|youtu\.be/)([a-zA-Z0-9_-]{11})"
    m = re.search(yt_pattern, original)
    if m:
        vid_id = m.group(1)
        return {
            "embed_url": f"https://www.youtube.com/embed/{vid_id}",
            "provider": "youtube",
            "video_id": vid_id,
            "original_url": original,
        }

    # Vimeo patterns
    vimeo_pattern = r"vimeo\.com/(?:video/)?(\d+)"
    m = re.search(vimeo_pattern, original)
    if m:
        vid_id = m.group(1)
        return {
            "embed_url": f"https://player.vimeo.com/video/{vid_id}",
            "provider": "vimeo",
            "video_id": vid_id,
            "original_url": original,
        }

    # Provider hint with unrecognised URL format
    if provider in ("youtube", "vimeo"):
        return {
            "embed_url": original,
            "provider": provider,
            "video_id": "",
            "original_url": original,
        }

    # Direct video file
    return {
        "embed_url": original,
        "provider": "direct",
        "video_id": "",
        "original_url": original,
    }


def score_quiz_attempt(
    questions: List[Dict],
    answers: List[int],
) -> Tuple[float, int]:
    """
    Scores a quiz attempt.

    Args:
        questions: List of question dicts with 'correct_index' key.
        answers: List of selected option indices (one per question).

    Returns:
        (score_percent: float, correct_count: int)
    """
    if not questions:
        return 0.0, 0

    correct = 0
    for i, question in enumerate(questions):
        if i < len(answers) and answers[i] == question.get("correct_index"):
            correct += 1

    score = (correct / len(questions)) * 100
    return round(score, 1), correct


def generate_certificate_hash(
    user_id: str,
    course_id: str,
    issued_at: datetime,
) -> str:
    """
    Generates a unique, non-guessable certificate hash.
    Includes a random component so identical (user, course) at the same second
    still produce different hashes.
    """
    nonce = secrets.token_hex(8)
    data = f"{user_id}:{course_id}:{issued_at.isoformat()}:{nonce}"
    return hashlib.sha256(data.encode()).hexdigest()[:32]


def generate_certificate_pdf(
    user_name: str,
    course_title: str,
    issued_at: datetime,
    cert_hash: str,
) -> bytes:
    """
    Generates a PDF certificate using ReportLab.

    Returns raw PDF bytes suitable for a StreamingResponse.
    """
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import landscape, letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        HRFlowable,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
    )

    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        leftMargin=1.0 * inch,
        rightMargin=1.0 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )

    styles = getSampleStyleSheet()
    center = TA_CENTER

    def style(name: str, base: str = "Normal", **kw) -> ParagraphStyle:
        kw.setdefault("alignment", center)
        return ParagraphStyle(name, parent=styles[base], **kw)

    navy = colors.HexColor("#1e3a5f")
    steel = colors.HexColor("#4a6fa5")
    gray = colors.HexColor("#555555")
    light_gray = colors.HexColor("#888888")
    white_board = colors.HexColor("#f8fafc")

    story = [
        Spacer(1, 0.1 * inch),
        Paragraph(
            "CRYPTO TRADE HUB",
            style("LogoTitle", fontSize=38, textColor=navy, fontName="Helvetica-Bold"),
        ),
        Paragraph(
            "Centro de Educação em Trading",
            style("SubLogo", fontSize=13, textColor=steel),
        ),
        Spacer(1, 0.1 * inch),
        HRFlowable(width="90%", thickness=2, color=navy),
        Spacer(1, 0.25 * inch),
        Paragraph(
            "CERTIFICADO DE CONCLUSÃO",
            style("CertLabel", fontSize=20, textColor=light_gray, fontName="Helvetica"),
        ),
        Spacer(1, 0.2 * inch),
        Paragraph(
            "Certificamos que",
            style("Certify", fontSize=15, textColor=gray),
        ),
        Spacer(1, 0.1 * inch),
        Paragraph(
            user_name,
            style("Name", fontSize=30, textColor=navy, fontName="Helvetica-Bold"),
        ),
        Spacer(1, 0.1 * inch),
        Paragraph(
            "concluiu com êxito o curso",
            style("Certify2", fontSize=15, textColor=gray),
        ),
        Spacer(1, 0.1 * inch),
        Paragraph(
            f"<b>{course_title}</b>",
            style("CourseTitle", fontSize=20, textColor=steel),
        ),
        Spacer(1, 0.35 * inch),
        HRFlowable(width="55%", thickness=1, color=colors.HexColor("#cccccc")),
        Spacer(1, 0.12 * inch),
        Paragraph(
            f"Emitido em {issued_at.strftime('%d de %B de %Y') if hasattr(issued_at, 'strftime') else str(issued_at)}",
            style("Date", fontSize=14, textColor=gray),
        ),
        Spacer(1, 0.06 * inch),
        Paragraph(
            f"Certificado N.º {cert_hash.upper()[:16]}",
            style("Hash", fontSize=9, textColor=light_gray),
        ),
    ]

    doc.build(story)
    return buffer.getvalue()
