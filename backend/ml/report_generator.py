"""
DPDP Act 2023 compliant PDF report generation.

Two report types:
    session — full detail for one session_id
    weekly  — aggregate summary for the last 7 days

Both reports only ever include already-masked data (prompt_masked,
never raw prompts) — audit_logs never stored raw PII in the first
place (see security/pii_detector.py), so there's nothing extra to
scrub here; the compliance guarantee was established at write time.
"""

import io
from datetime import datetime, timedelta, timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
)

DPDP_STATEMENT = (
    "This report is generated in compliance with India's Digital Personal Data "
    "Protection Act, 2023 (DPDP Act). All personally identifiable information "
    "(PII) referenced in this report has been automatically detected and masked "
    "prior to storage — no raw personal data is retained in the underlying "
    "system or reproduced in this document. Audit records are retained for "
    "regulatory traceability. Data subjects may request erasure of their "
    "conversation history at any time; audit trail entries are retained "
    "separately as required for compliance purposes."
)


def _base_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="ReportTitle", fontSize=20, leading=26, spaceAfter=10, textColor=colors.HexColor("#1B1B2F"),
    ))
    styles.add(ParagraphStyle(
        name="ReportSubtitle", fontSize=11, textColor=colors.grey, spaceAfter=20,
    ))
    styles.add(ParagraphStyle(
        name="SectionHeading", fontSize=14, spaceBefore=18, spaceAfter=8,
        textColor=colors.HexColor("#3ae6f2"),
    ))
    styles.add(ParagraphStyle(
        name="ComplianceText", fontSize=9, textColor=colors.grey, leading=13,
    ))
    return styles


def _status_color(status: str):
    if status == "Safe":
        return colors.HexColor("#10B981")
    if status == "PII Detected":
        return colors.HexColor("#F59E0B")
    return colors.HexColor("#EF4444")  # Prompt Injection / Harmful / Jailbreak


def _build_log_table(logs: list[dict]):
    header = ["Timestamp", "Status", "Threat Tier", "Model", "Masked Prompt"]
    rows = [header]

    for log in logs:
        ts = log["timestamp"].strftime("%Y-%m-%d %H:%M:%S UTC") if log.get("timestamp") else "—"
        prompt_preview = (log.get("prompt_masked") or "")[:60]
        if len(log.get("prompt_masked") or "") > 60:
            prompt_preview += "..."

        rows.append([
            ts,
            log.get("status", "—"),
            str(log.get("threat_tier", "—")),
            log.get("model_used") or "—",
            prompt_preview,
        ])

    table = Table(rows, colWidths=[1.3*inch, 1.1*inch, 0.7*inch, 1.0*inch, 2.4*inch], repeatRows=1)

    style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#23233A")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
    ]
    for i, log in enumerate(logs, start=1):
        style.append(("TEXTCOLOR", (1, i), (1, i), _status_color(log.get("status", ""))))

    table.setStyle(TableStyle(style))
    return table


def _compliance_footer(styles):
    return [
        Spacer(1, 24),
        Paragraph("Compliance Statement", styles["SectionHeading"]),
        Paragraph(DPDP_STATEMENT, styles["ComplianceText"]),
        Spacer(1, 12),
        Paragraph(
            f"Report generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
            styles["ComplianceText"],
        ),
    ]


async def generate_session_report(db, session_id: str) -> bytes:
    """Full audit detail for one session, as PDF bytes."""
    logs = [doc async for doc in db.audit_logs.find({"session_id": session_id}).sort("timestamp", 1)]

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.75*inch, bottomMargin=0.75*inch)
    styles = _base_styles()
    story = []

    story.append(Paragraph("LLM Guardrail — Session Report", styles["ReportTitle"]))
    story.append(Paragraph(f"Session ID: {session_id}", styles["ReportSubtitle"]))

    if not logs:
        story.append(Paragraph("No audit log entries found for this session.", styles["Normal"]))
    else:
        total = len(logs)
        blocked = sum(1 for l in logs if l["status"] in ("Prompt Injection", "Harmful", "Jailbreak"))
        pii = sum(1 for l in logs if l["status"] == "PII Detected")
        safe = total - blocked - pii

        story.append(Paragraph("Summary", styles["SectionHeading"]))
        summary_table = Table(
            [["Total Requests", "Safe", "PII Masked", "Blocked"],
             [str(total), str(safe), str(pii), str(blocked)]],
            colWidths=[1.6*inch]*4,
        )
        summary_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#23233A")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ]))
        story.append(summary_table)

        story.append(Paragraph("Request Log", styles["SectionHeading"]))
        story.append(_build_log_table(logs))

    story.extend(_compliance_footer(styles))

    doc.build(story)
    buffer.seek(0)
    return buffer.read()


async def generate_weekly_report(db) -> bytes:
    """Aggregate summary of the last 7 days, as PDF bytes."""
    since = datetime.now(timezone.utc) - timedelta(days=7)
    logs = [doc async for doc in db.audit_logs.find({"timestamp": {"$gte": since}}).sort("timestamp", 1)]

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.75*inch, bottomMargin=0.75*inch)
    styles = _base_styles()
    story = []

    story.append(Paragraph("LLM Guardrail — Weekly Report", styles["ReportTitle"]))
    story.append(Paragraph(
        f"{since.strftime('%Y-%m-%d')} to {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
        styles["ReportSubtitle"],
    ))

    if not logs:
        story.append(Paragraph("No requests recorded in this period.", styles["Normal"]))
    else:
        total = len(logs)
        blocked = sum(1 for l in logs if l["status"] in ("Prompt Injection", "Harmful", "Jailbreak"))
        pii = sum(1 for l in logs if l["status"] == "PII Detected")
        safe = total - blocked - pii
        unique_sessions = len({l["session_id"] for l in logs})
        unique_users = len({l["user_id"] for l in logs})

        story.append(Paragraph("Summary", styles["SectionHeading"]))
        summary_table = Table(
            [["Total Requests", "Unique Sessions", "Unique Users", "Blocked"],
             [str(total), str(unique_sessions), str(unique_users), str(blocked)]],
            colWidths=[1.6*inch]*4,
        )
        summary_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#23233A")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ]))
        story.append(summary_table)

        breakdown_table = Table(
            [["Safe", "PII Masked", "Blocked"], [str(safe), str(pii), str(blocked)]],
            colWidths=[2.13*inch]*3,
        )
        breakdown_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#23233A")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ]))
        story.append(Spacer(1, 12))
        story.append(Paragraph("Threat Breakdown", styles["SectionHeading"]))
        story.append(breakdown_table)

        story.append(PageBreak())
        story.append(Paragraph("Full Request Log", styles["SectionHeading"]))
        story.append(_build_log_table(logs))

    story.extend(_compliance_footer(styles))

    doc.build(story)
    buffer.seek(0)
    return buffer.read()
