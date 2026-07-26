"""Report endpoints: branded, digitally-signed PDF exports.

Access (Administrator always allowed): Manager, Accountant.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from api.deps import get_current_user, get_report_service, require_roles
from models.user import Role, User
from services.report_service import ReportService

router = APIRouter(prefix="/reports", tags=["reports"])

can_view = require_roles(Role.MANAGER, Role.ACCOUNTANT)


@router.get("/{report_key}/pdf", dependencies=[Depends(can_view)])
async def report_pdf(
    report_key: str,
    company: str | None = None,
    fiscal_year: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    warehouse: str | None = None,
    service: ReportService = Depends(get_report_service),
    user: User = Depends(get_current_user),
) -> Response:
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    filename, pdf = await service.generate_pdf(
        report_key,
        company=company,
        fiscal_year=fiscal_year,
        from_date=from_date,
        to_date=to_date,
        warehouse=warehouse,
        generated_by=user.full_name or user.email,
        generated_at=generated_at,
    )
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
