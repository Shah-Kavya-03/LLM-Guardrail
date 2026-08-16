"""
GET /report/download?type=session&id=...
GET /report/download?type=weekly

Generates a DPDP Act 2023 compliant PDF report and streams it back
as a file download.
"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
import io

from database.connection import get_db
from ml.report_generator import generate_session_report, generate_weekly_report

router = APIRouter(prefix="/report", tags=["Reports"])


@router.get("/download")
async def download_report(
    type: str = Query(..., pattern="^(session|weekly)$"),
    id: str | None = None,
):
    db = get_db()

    if type == "session":
        if not id:
            raise HTTPException(status_code=400, detail="`id` (session_id) is required when type=session.")
        pdf_bytes = await generate_session_report(db, id)
        filename = f"guardrail_session_{id}.pdf"

    else:  # type == "weekly"
        pdf_bytes = await generate_weekly_report(db)
        filename = "guardrail_weekly_report.pdf"

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
