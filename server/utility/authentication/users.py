from datetime import datetime, timedelta, timezone

import jwt
from dependency_injector.wiring import Provide, inject
from pydantic import BaseModel
from fastapi import Depends

from containers import Container
from models.user import User
from resource_access.users_ra import UsersRA
from utility.communication.email import Emailer
from utility.communication.email_templates import agreement_signed_notification_email

from .google_login import GoogleIdentification
from .xhost_auth import XhostIdentification

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24


class AccessTokenPayload(BaseModel):
    sub: str
    email: str
    name: str
    picture: str


def get_access_token_expire_minutes():
    return ACCESS_TOKEN_EXPIRE_MINUTES


@inject
def encode_access_token(
    data: dict,
    expires_delta: timedelta | None = None,
    access_token_secret_key: str = Depends(Provide[Container.config.auth.access_token_secret_key]),
):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, access_token_secret_key, algorithm=ALGORITHM)
    return encoded_jwt


@inject
def decode_access_token(
    token: str, access_token_secret_key: str = Depends(Provide[Container.config.auth.access_token_secret_key])
):
    payload = jwt.decode(token, access_token_secret_key, algorithms=[ALGORITHM])
    return payload


def create_user_from_google_id(google_identification: GoogleIdentification):
    return User(
        email=google_identification.email,
        email_verified=google_identification.email_verified,
        name=google_identification.name,
        picture=google_identification.picture,
        google_sub=google_identification.sub,
    )


def create_user_from_xhost_identification(xhost_identification: XhostIdentification):
    # xhost verified the visitor's Google identity for us (see utility/authentication/xhost_auth.py).
    # email_verified=True since it came from Google via xhost's own verified dance.
    return User(
        email=xhost_identification.email,
        email_verified=True,
        name=xhost_identification.name,
        picture="",
    )


def create_access_token_payload_from_user(user: User):
    return AccessTokenPayload(
        sub=str(user.id),
        email=user.email,
        name=user.name,
        picture=user.picture,
    )


def create_empty_speaker_user(email: str):
    return User(email=email, email_verified=False, name=f"Pre Approved Speaker {email}", picture="")


@inject
def record_user_agreement(
    user: User,
    users_ra: UsersRA = Depends(Provide[Container.users_ra]),
    emailer: Emailer = Depends(Provide[Container.emailer]),
):
    # only if the user had not signed the agreement yet
    first_time_signer = user.agreement_signed_at is None
    agreement_version = "v2"  # Could be made dynamic in a more complex system
    user.agreement_signed_version = agreement_version
    user.agreement_signed_at = datetime.now(timezone.utc)
    users_ra.upsert(user)

    if first_time_signer:
        emailer.send_to_user(
            user,
            agreement_signed_notification_email["subject"],
            agreement_signed_notification_email["body"].format(
                name=user.name,
                agreement_version=agreement_version,
            ),
        )
