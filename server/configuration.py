import logging

from environs import Env

from version import __version__

env = Env()
env.read_env()


def configure_logging(container):
    logging.basicConfig()
    if container.config.debug_mode():
        logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)


# For out-of-di usage (See Async DB module for the CRUD api stack)
# Supports both this project's own DB_CONNECTION_STR and xhost's built-in
# DATABASE_URL (auto-injected per channel) - DB_CONNECTION_STR wins if both are set.
def get_db_connection_str() -> str:
    return env("DB_CONNECTION_STR", default=None) or env("DATABASE_URL")


def configure(container: "Container"):
    container.config.version.from_value(__version__)
    container.config.web_client_dist_folder.from_value(env("WEB_CLIENT_DIST_FOLDER", default="web_client_dist"))

    container.config.db.connection_str.from_value(get_db_connection_str())

    container.config.cors.allow_origins.from_value(env.list("CORS_ALLOW_ORIGINS", []))
    # AUTH_MODE selects which login flow the client offers: "google" (default) or "xhost"
    # (xhost's built-in Google sign-in via the __Host-xhost_id identity cookie).
    # Both code paths are always wired up server-side regardless of this flag.
    container.config.auth.mode.from_value(env("AUTH_MODE", default="google"))
    # Required to verify the xhost identity cookie's "aud" claim - must equal the exact
    # channel hostname (e.g. crowd-recital-yoad.xhostd.com). Only needed when AUTH_MODE=xhost.
    container.config.auth.xhost_audience.from_value(env("AUTH_XHOST_AUDIENCE", default=None))
    # Not required when AUTH_MODE=xhost
    container.config.auth.google.client_id.from_value(env("GOOGLE_CLIENT_ID", default=""))
    container.config.auth.delegated_identity_secret_key.from_value(env("DELEGATED_IDENTITY_SECRET_KEY"))
    container.config.auth.access_token_secret_key.from_value(env("ACCESS_TOKEN_SECRET_KEY"))
    container.config.auth.disable_auto_speaker_approve.from_value(env.bool("DISABLE_AUTO_SPEAKER_APPROVAL"))
    container.config.auth.dev_auto_login_user_email.from_value(env("DEV_AUTO_LOGIN_USER_EMAIL", default=None))

    container.config.email.sender_address.from_value(env("EMAIL_SENDER_ADDRESS"))
    container.config.email.reply_to_address.from_value(env("EMAIL_REPLY_TO_ADDRESS", env("EMAIL_SENDER_ADDRESS")))

    container.config.data.root_folder.from_value(env("ROOT_DATA_FOLDER", default="data"))
    container.config.data.content_s3_bucket.from_value(env("CONTENT_STORAGE_S3_BUCKET"))
    container.config.data.content_s3_disabled.from_value(env.bool("CONTENT_DISABLE_S3_UPLOAD", default=False))

    container.config.stats.leaderboard_depth.from_value(env.int("LEADERBOARD_DEPTH", default=20))

    container.config.help.basic_guide_yt_video_id.from_value(env("HELP_BASIC_GUIDE_YT_VIDEO_ID", default=None))
    container.config.help.faq_wp_api_url.from_value(env("HELP_FAQ_WP_API_URL", default=None))

    container.config.jobs.session_finalization.disabled.from_value(
        env.bool("JOB_SESSION_FINALIZATION_DISABLED", default=False)
    )
    container.config.jobs.session_finalization.interval_sec.from_value(
        env.int("JOB_SESSION_FINALIZATION_INTERVAL_SEC", default=120)
    )

    container.config.analytics.posthog.api_key.from_value(env("PUBLIC_POSTHOG_KEY"))
    container.config.analytics.posthog.host.from_value(env("PUBLIC_POSTHOG_HOST"))

    container.config.client.disable_soup.from_value(env.bool("DISABLE_SOUP", default=False))

    container.config.debug_mode.from_value(env.bool("DEBUG", default=False))

    configure_logging(container)

    return container
