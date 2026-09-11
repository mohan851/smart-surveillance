"""
PDF report generation — generates a per-user surveillance report.
"""
from io import BytesIO
from datetime import datetime
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import desc

from api.middleware import get_current_user
from database.db import session_scope
from database.models import Detection

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/pdf")
def download_pdf(current_user=Depends(get_current_user)):
    """Generate a PDF report of the current user's detection history."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

    uid = current_user["id"]
    with session_scope() as s:
        rows = s.query(Detection).filter_by(user_id=uid) \
                                 .order_by(desc(Detection.timestamp)) \
                                 .limit(500).all()
        uname = current_user["username"]

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, title=f"Agent Eye Report - {uname}")
    styles = getSampleStyleSheet()
    story  = [
        Paragraph(f"<b>Agent Eye Surveillance Report</b>", styles["Title"]),
        Paragraph(f"User: <b>{uname}</b> &nbsp;&nbsp; Generated: {datetime.utcnow():%Y-%m-%d %H:%M UTC}",
                  styles["Normal"]),
        Spacer(1, 12),
    ]
    if not rows:
        story.append(Paragraph("No detections recorded yet.", styles["Italic"]))
    else:
        data = [["#", "Timestamp (UTC)", "Label", "Confidence", "Camera"]]
        for i, r in enumerate(rows, 1):
            data.append([
                str(i),
                r.timestamp.strftime("%Y-%m-%d %H:%M:%S") if r.timestamp else "-",
                r.label,
                f"{r.confidence}%",
                r.camera_source or "-",
            ])
        t = Table(data, hAlign="LEFT")
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0d6efd")),
            ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
            ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",   (0, 0), (-1, -1), 9),
            ("GRID",       (0, 0), (-1, -1), 0.25, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.white, colors.HexColor("#f6f8fa")]),
        ]))
        story.append(t)

    doc.build(story)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="agent_eye_report_{uname}.pdf"'},
    )
