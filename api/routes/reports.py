from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from datetime import datetime
import os
from api.middleware import get_current_user
from database.models import get_all_detections
from config import BASE_DIR

router = APIRouter()

def generate_pdf(detections: list, filepath: str):
    doc    = SimpleDocTemplate(filepath, pagesize=A4)
    styles = getSampleStyleSheet()
    story  = []

    # ── Title ────────────────────────────────────────────
    story.append(Paragraph("Smart Surveillance Report", styles["Title"]))
    story.append(Paragraph(
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        styles["Normal"]
    ))
    story.append(Spacer(1, 20))

    # ── Summary ──────────────────────────────────────────
    total    = len(detections)
    intruders = sum(1 for d in detections if d["type"] == "intruder")
    story.append(Paragraph(f"Total detections: {total}", styles["Normal"]))
    story.append(Paragraph(f"Intruder alerts: {intruders}", styles["Normal"]))
    story.append(Spacer(1, 20))

    # ── Table ────────────────────────────────────────────
    headers = ["ID", "Camera", "Type", "Label", "Timestamp"]
    rows    = [headers]
    for d in detections:
        rows.append([
            str(d["id"]),
            str(d["camera_id"]),
            d["type"],
            d["label"] or "-",
            d["timestamp"]
        ])

    table = Table(rows, colWidths=[40, 60, 80, 120, 160])
    table.setStyle(TableStyle([
        ("BACKGROUND",  (0,0), (-1,0), colors.HexColor("#2C2C2A")),
        ("TEXTCOLOR",   (0,0), (-1,0), colors.white),
        ("FONTNAME",    (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",    (0,0), (-1,-1), 9),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#F1EFE8")]),
        ("GRID",        (0,0), (-1,-1), 0.5, colors.HexColor("#B4B2A9")),
        ("ALIGN",       (0,0), (-1,-1), "CENTER"),
        ("VALIGN",      (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING",  (0,0), (-1,-1), 6),
        ("BOTTOMPADDING",(0,0), (-1,-1), 6),
    ]))
    story.append(table)
    doc.build(story)

# ── Generate + download report ───────────────────────────
@router.get("/generate")
def generate_report(
    limit        : int = 500,
    current_user      = Depends(get_current_user)
):
    detections = get_all_detections(limit=limit)
    timestamp  = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename   = f"report_{timestamp}.pdf"
    filepath   = os.path.join(BASE_DIR, filename)

    generate_pdf(detections, filepath)

    return FileResponse(
        path             = filepath,
        media_type       = "application/pdf",
        filename         = filename
    )