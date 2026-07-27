from typing import Annotated
from uuid import UUID

from dependency_injector.wiring import Provide, inject
from fastapi import Cookie, Depends, HTTPException, Header, Response, status
from fastapi.security import APIKeyCookie, HTTPAuthorizationCredentials, HTTPBearer, APIKeyHeader
from jwt.exceptions import InvalidTokenError
from nanoid import generate
from pydantic import BaseModel

from containers import Container
from models.user import User, UserGroups
from resource_access.users_ra import UsersRA
from utility.authentication.invites import validate_invite_value
from utility.authentication.users import (
    create_user_from_xhost_identification,
    decode_access_token,
    get_access_token_expire_minutes,
)
from utility.authentication.xhost_auth import XhostIdentification, get_xhost_identification

AUTH_COOKIE_NAME = "access_token"

http_bearer_security = HTTPBearer(auto_error=False)
api_key_cookie_security = APIKeyCookie(name=AUTH_COOKIE_NAME, auto_error=False)
identity_delegation_security = APIKeyHeader(name="x-delegation-secret-key", auto_error=False)

AuthCookie = Annotated[str | None, Cookie(alias=AUTH_COOKIE_NAME, alias_priority=1)]
CredentialsBearer = Annotated[HTTPAuthorizationCredentials, Depends(http_bearer_security)]
CredentialsCookie = Annotated[str, Depends(api_key_cookie_security)]
IdentityDelegationSecurity = Annotated[str, Depends(identity_delegation_security)]
DelegatedUserEmail = Annotated[str, Header(alias=f"x-delegated-user-email")]


def set_access_token_cookie(response: Response, access_token: str):
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=access_token,
        max_age=get_access_token_expire_minutes() * 60,
        httponly=True,
        secure=True,
        samesite="strict",
    )


def unset_access_token_cookie(response: Response):
    response.delete_cookie(
        key=AUTH_COOKIE_NAME,
        httponly=True,
        secure=True,
        samesite="strict",
    )


class AuthenticationErrorDetails(BaseModel):
    google_client_id: str
    g_csrf_token: str


@inject
def get_authenticated_user_id(
    credentials_bearer: CredentialsBearer,
    credentials_cookie: CredentialsCookie,
) -> str:
    user_id: str = None
    try:
        if credentials_bearer:
            credentials = credentials_bearer.credentials
        else:
            credentials = credentials_cookie
        if credentials:
            payload = decode_access_token(credentials)
            user_id = payload.get("sub")
            return user_id
    except InvalidTokenError:
        pass

    return None


@inject
def get_delegated_user_email(
    delegation_secret_key: IdentityDelegationSecurity,
    delegated_email: DelegatedUserEmail = None,
    delegated_identity_secret_key: str = Depends(Provide[Container.config.auth.delegated_identity_secret_key]),
) -> str:
    if delegation_secret_key == delegated_identity_secret_key and delegated_email:
        return delegated_email

    return None


@inject
async def get_valid_user(
    response: Response,
    authenticated_user_id: Annotated[str, Depends(get_authenticated_user_id)],
    delegated_user_email: Annotated[str, Depends(get_delegated_user_email)],
    xhost_identification: Annotated[XhostIdentification | None, Depends(get_xhost_identification)],
    google_client_id: str = Depends(Provide[Container.config.auth.google.client_id]),
    dev_auto_login_user_email: str = Depends(Provide[Container.config.auth.dev_auto_login_user_email]),
    users_ra: UsersRA = Depends(Provide[Container.users_ra]),
):
    user: User = None
    if authenticated_user_id:
        user = users_ra.get_by_id(authenticated_user_id)
    elif delegated_user_email:
        user = users_ra.get_by_email(delegated_user_email)
    elif xhost_identification:
        # xhost verified the visitor's identity (see utility/authentication/xhost_auth.py) -
        # find or create the local user record by email, mirroring the Google login flow's
        # find-or-create logic (routers/users.py: login_user), minus the CSRF/form dance
        # since the identity already arrived pre-verified via the xhost cookie.
        user = users_ra.get_by_email(xhost_identification.email)
        if not user:
            new_user = create_user_from_xhost_identification(xhost_identification)
            if should_grant_speaker_permission(new_user, invite_value=None):
                new_user.group = "speaker"
            user = users_ra.upsert(new_user)
            user = users_ra.get_by_email(xhost_identification.email)
    elif dev_auto_login_user_email:
        print(f"WARNING: Using DEV_AUTO_LOGIN_USER_EMAIL for development - auto-logging in user: {dev_auto_login_user_email}")
        user = users_ra.get_by_email(dev_auto_login_user_email)
        if not user:
            print(f"ERROR: DEV_AUTO_LOGIN_USER_EMAIL not found in DB - auto-logging in user: {dev_auto_login_user_email}")
    else:  # Not authenticated
        auth_error_details = AuthenticationErrorDetails(
            google_client_id=google_client_id, g_csrf_token=generate(size=16)
        )
        auth_error_details_dump = auth_error_details.model_dump()
        response.set_cookie("g_csrf_token", value=auth_error_details.g_csrf_token)
        headers = {
            "set-cookie": response.headers["set-cookie"],
            "Cache-Control": "no-store",
            "x-g-csrf-token": auth_error_details.g_csrf_token,
        }
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=auth_error_details_dump, headers=headers)

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return user


def has_admin_permission(user: User):
    return user.group == UserGroups.ADMIN


def has_speaker_permission(user: User):
    return user.group == UserGroups.SPEAKER or has_admin_permission(user)


@inject
def should_grant_speaker_permission(
    user: User,  # not looking at the user ATM
    invite_value: str,
    disable_auto_speaker_approve: bool = Provide[Container.config.auth.disable_auto_speaker_approve],
):
    if not disable_auto_speaker_approve:  # Always approve as speaker
        return True
    elif validate_invite_value(invite_value):
        return True

    return False


async def get_speaker_user(user: Annotated[User, Depends(get_valid_user)]):
    if not has_speaker_permission(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is not an authorized speaker")
    return user


async def get_admin_user(user: Annotated[User, Depends(get_valid_user)]):
    if not has_admin_permission(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is not an authorized admin")
    return user
