"""Authentication endpoints. Thin controllers — logic lives in AuthService."""

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from api.deps import get_auth_service, get_current_user
from models.user import User
from schemas.auth import Token
from schemas.user import UserRead
from services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    auth_service: AuthService = Depends(get_auth_service),
) -> Token:
    """OAuth2 password flow. `username` is the user's email."""
    token = auth_service.login(form_data.username, form_data.password)
    return Token(access_token=token)


@router.post("/logout", status_code=status.HTTP_200_OK)
def logout(current_user: User = Depends(get_current_user)) -> dict:
    """Stateless JWT: the client discards the token. Provided for symmetry/audit."""
    return {"detail": "Logged out"}


@router.get("/me", response_model=UserRead)
def read_current_user(current_user: User = Depends(get_current_user)) -> User:
    return current_user
