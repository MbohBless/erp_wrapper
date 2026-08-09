"""Authentication endpoints. Thin controllers — logic lives in AuthService."""

from fastapi import APIRouter, Depends, Request, status
from fastapi.security import OAuth2PasswordRequestForm

from api.deps import get_auth_service, get_current_user
from models.user import User
from schemas.auth import RefreshRequest, Token
from schemas.user import UserRead
from services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


def _client(request: Request) -> tuple[str, str]:
    """Address and user agent, recorded against the session that is created."""
    fwd = request.headers.get("x-forwarded-for", "")
    ip = fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "")
    return ip, request.headers.get("user-agent", "")


@router.post("/login", response_model=Token)
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    auth_service: AuthService = Depends(get_auth_service),
) -> Token:
    """OAuth2 password flow. `username` is the user's email."""
    ip, ua = _client(request)
    user, access, refresh, expires_in = auth_service.login(
        form_data.username, form_data.password, ip=ip, user_agent=ua
    )
    # Name the actor on the audit entry. No dependency has run to identify them
    # — that is the whole point of a login — so the route publishes it, the same
    # way get_current_user does for authenticated requests.
    request.scope["audit_actor"] = {
        "id": user.id,
        "email": user.email,
        "role": str(user.role),
    }
    return Token(access_token=access, refresh_token=refresh, expires_in=expires_in)


@router.post("/refresh", response_model=Token)
def refresh(
    request: Request,
    body: RefreshRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> Token:
    """Exchange a refresh token for a fresh pair.

    Unauthenticated by design: it is called precisely when the access token has
    expired, so requiring one would defeat the purpose. The refresh token is the
    credential, and it is single-use — see AuthService.refresh.
    """
    ip, ua = _client(request)
    access, new_refresh, expires_in = auth_service.refresh(
        body.refresh_token, ip=ip, user_agent=ua
    )
    return Token(
        access_token=access, refresh_token=new_refresh, expires_in=expires_in
    )


@router.post("/logout", status_code=status.HTTP_200_OK)
def logout(
    body: RefreshRequest | None = None,
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> dict:
    """Revoke the session server-side.

    Previously a no-op that told the client to forget its JWT — which left the
    refresh token valid for weeks afterwards. Passing the refresh token revokes
    that session; omitting it revokes every session for the user.
    """
    auth_service.logout(body.refresh_token if body else None, current_user)
    return {"detail": "Logged out"}


@router.get("/me", response_model=UserRead)
def read_current_user(current_user: User = Depends(get_current_user)) -> User:
    return current_user
