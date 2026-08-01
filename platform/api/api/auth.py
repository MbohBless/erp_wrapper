"""Platform operator auth + operator management."""

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from api.deps import (
    get_auth_service,
    get_current_operator,
    get_platform_user_service,
    owner_only,
)
from models.platform_user import PlatformUser
from schemas.auth import (
    PlatformUserCreate,
    PlatformUserRead,
    PlatformUserUpdate,
    Token,
)
from services.auth_service import PlatformAuthService, PlatformUserService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    service: PlatformAuthService = Depends(get_auth_service),
) -> Token:
    return Token(access_token=service.login(form_data.username, form_data.password))


@router.get("/me", response_model=PlatformUserRead)
def me(operator: PlatformUser = Depends(get_current_operator)) -> PlatformUser:
    return operator


operators = APIRouter(prefix="/operators", tags=["operators"])


@operators.get("", response_model=list[PlatformUserRead], dependencies=[Depends(owner_only)])
def list_operators(
    service: PlatformUserService = Depends(get_platform_user_service),
) -> list[PlatformUser]:
    return service.list()


@operators.post(
    "",
    response_model=PlatformUserRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(owner_only)],
)
def create_operator(
    data: PlatformUserCreate,
    service: PlatformUserService = Depends(get_platform_user_service),
) -> PlatformUser:
    return service.create(data)


@operators.patch(
    "/{user_id}", response_model=PlatformUserRead, dependencies=[Depends(owner_only)]
)
def update_operator(
    user_id: int,
    data: PlatformUserUpdate,
    service: PlatformUserService = Depends(get_platform_user_service),
) -> PlatformUser:
    return service.update(user_id, data)


@operators.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(owner_only)],
)
def delete_operator(
    user_id: int,
    service: PlatformUserService = Depends(get_platform_user_service),
) -> None:
    service.delete(user_id)
