import pathlib

from dependency_injector.wiring import Provide, inject
from fastapi import FastAPI, Depends
from fastapi.responses import PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from containers import Container

env = FastAPI()


@inject
def get_web_client_env_app() -> FastAPI:
    return env


class ClientConfig(BaseModel):
    version: str

    auth_mode: str = "google"
    auth_google_client_id: str

    audio_segment_upload_length_seconds: int

    analytics_posthog_api_key: str | None = None
    analytics_posthog_host: str | None = None

    help_basic_guide_yt_video_id: str | None = None
    help_faq_wp_api_url: str | None = None

    disable_soup: str = "0"


class ClientEnv(BaseModel):
    config: ClientConfig


@env.get("/config.js", response_class=PlainTextResponse)
@inject
def get_env_config(
    # For safety - we bother to list each configuration entry we want to expose,
    # and in multiple places - so exposing anything from the server env to the client
    # is (hopefully) a deliberate decision.
    version: str = Depends(Provide[Container.config.version]),
    auth_mode: str = Depends(Provide[Container.config.auth.mode]),
    google_client_id: str = Depends(Provide[Container.config.auth.google.client_id]),
    posthog_api_key: str = Depends(Provide[Container.config.analytics.posthog.api_key]),
    posthog_host: str = Depends(Provide[Container.config.analytics.posthog.host]),
    help_basic_guide_yt_video_id: str = Depends(Provide[Container.config.help.basic_guide_yt_video_id]),
    help_faq_wp_api_url: str = Depends(Provide[Container.config.help.faq_wp_api_url]),
    disable_soup: str = Depends(Provide[Container.config.client.disable_soup]),
) -> str:
    client_env = ClientEnv(
        config=ClientConfig(
            version=version,
            auth_mode=auth_mode,
            auth_google_client_id=google_client_id,
            audio_segment_upload_length_seconds=10,
            analytics_posthog_api_key=posthog_api_key,
            analytics_posthog_host=posthog_host,
            help_basic_guide_yt_video_id=help_basic_guide_yt_video_id,
            help_faq_wp_api_url=help_faq_wp_api_url,
            disable_soup="1" if disable_soup else "0",
        )
    )
    config_script_content = f"window.__env__ = {client_env.model_dump_json()}"
    return PlainTextResponse(content=config_script_content, headers={"Content-Type": "application/javascript"})


@inject
def get_web_client_app(dist_folder: str = Provide[Container.config.web_client_dist_folder]) -> FastAPI:
    return StaticFiles(directory=pathlib.Path(dist_folder), html=True)
