"""User CRUD endpoints with RBAC. Thin controllers — logic lives in UserService."""

from fastapi import APIRouter, Depends, HTTPException, status

from api.deps import get_current_user, get_user_service, require_roles
from models.user import Role, User, assignable_roles
from schemas.user import UserCreate, UserRead, UserUpdate
from services.user_service import UserService

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "",
    response_model=list[UserRead],
    dependencies=[Depends(require_roles(Role.ADMINISTRATOR))],
)
def list_users(
    skip: int = 0,
    limit: int = 100,
    service: UserService = Depends(get_user_service),
) -> list[User]:
    return service.list(skip, limit)


@router.post(
    "",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(Role.ADMINISTRATOR))],
)
def create_user(
    data: UserCreate,
    service: UserService = Depends(get_user_service),
) -> User:
    return service.create(data)


@router.get(
    "/roles",
    response_model=list[str],
    dependencies=[Depends(require_roles(Role.ADMINISTRATOR))],
)
def list_assignable_roles() -> list[str]:
    """Roles this deployment will hand out, for the user form to offer.

    Declared before `/{user_id}` so "roles" is read as this route rather than
    as a user id.
    """
    return [r.value for r in assignable_roles()]


@router.get("/{user_id}", response_model=UserRead)
def get_user(
    user_id: int,
    service: UserService = Depends(get_user_service),
    current_user: User = Depends(get_current_user),
) -> User:
    # Administrators may read anyone; other users may read only themselves.
    if str(current_user.role) != Role.ADMINISTRATOR.value and current_user.id != user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")
    return service.get(user_id)


@router.put(
    "/{user_id}",
    response_model=UserRead,
    dependencies=[Depends(require_roles(Role.ADMINISTRATOR))],
)
def update_user(
    user_id: int,
    data: UserUpdate,
    service: UserService = Depends(get_user_service),
) -> User:
    return service.update(user_id, data)


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_roles(Role.ADMINISTRATOR))],
)
def delete_user(
    user_id: int,
    service: UserService = Depends(get_user_service),
) -> None:
    service.delete(user_id)
