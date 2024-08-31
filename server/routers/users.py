from datetime import timedelta
from typing import Annotated

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Response, status
from fastapi.exceptions import HTTPException
from pydantic import BaseModel

from containers import Container
from models.user import User
from resource_access.users_ra import UsersRA
from utility.authentication.google_login import (GoogleIdentification,
                                                 get_google_identification,
                                                 validate_csrf_token)
from utility.authentication.users import (
    create_access_token_payload_from_user, create_user_from_google_id,
    encode_access_token, get_access_token_expire_minutes)

from .dependencies.users import (AuthCookie, get_valid_user,
                                 set_access_token_cookie,
                                 unset_access_token_cookie)

router = APIRouter()


class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    scope: str


@router.post("/login", dependencies=[Depends(validate_csrf_token)], response_model=LoginResponse)
@inject
async def login_user(
    google_identification: Annotated[GoogleIdentification, Depends(get_google_identification)],
    response: Response,
    users_ra: UsersRA = Depends(Provide[Container.users_ra]),
):
    derived_user_from_google_id = create_user_from_google_id(google_identification)
    # NOTE: we are not checking the email_verified flag
    # This is to simplify the implementation - but poses a security risk.
    # In theory - a user can take on an unverified email of another user and assume
    # control of that user.
    # In practice - this is not a big problem since we only use google login
    # and anyway not expect users to try and hack this system (famous last words - blame Yair.L)
    existing_user = users_ra.get_by_email(derived_user_from_google_id.email)

    if not existing_user:
        users_ra.upsert(derived_user_from_google_id)
    else:
        existing_user.picture = derived_user_from_google_id.picture
        existing_user.name = derived_user_from_google_id.name
        existing_user.email_verified = derived_user_from_google_id.email_verified
        users_ra.upsert(existing_user)

    user_email = existing_user.email if existing_user else derived_user_from_google_id.email
    existing_user = users_ra.get_by_email(user_email)

    user_token_payload = create_access_token_payload_from_user(existing_user)
    access_token_expires = timedelta(minutes=get_access_token_expire_minutes())
    access_token = encode_access_token(user_token_payload.model_dump(), expires_delta=access_token_expires)
    set_access_token_cookie(response, access_token)
    response.headers["Cache-Control"] = "no-store"
    response.status_code = status.HTTP_200_OK
    return LoginResponse(
        access_token=access_token, token_type="bearer", expires_in=int(access_token_expires.total_seconds()), scope=""
    )


@router.post("/logout")
def logout(response: Response, auth_cookie: AuthCookie = None):
    if auth_cookie:
        unset_access_token_cookie(response)
        response.headers["Cache-Control"] = "no-store"
        response.status_code = status.HTTP_200_OK
    return {"message": "Logged out"}


@router.get("/me", response_model=User)
@inject
def get_me(active_user: Annotated[User, Depends(get_valid_user)]):
    return active_user
