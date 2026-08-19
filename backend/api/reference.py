"""Reference data for form pickers. Any authenticated user.

Deliberately not role-gated beyond authentication: these are taxonomy labels
("Commercial", "Cameroon", "Nos") with no commercial content, and every form
that needs one is already guarded on its own write.

Its own prefix rather than `/customers/groups`, because that path would be
captured by `/customers/{customer_id}` — a route-ordering bug waiting to happen.
"""

from fastapi import APIRouter, Depends

from api.deps import get_current_user, get_reference_service
from schemas.reference import ReferenceOptions
from services.reference_service import ReferenceService

router = APIRouter(
    prefix="/reference",
    tags=["reference"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/options", response_model=ReferenceOptions)
async def options(
    service: ReferenceService = Depends(get_reference_service),
) -> ReferenceOptions:
    return await service.options()
