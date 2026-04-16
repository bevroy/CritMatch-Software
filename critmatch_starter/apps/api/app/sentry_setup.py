import os

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.utils import BadDsn


def init_sentry() -> None:
    dsn = (os.getenv("SENTRY_DSN") or "").strip()
    if not dsn:
        return

    try:
        sentry_sdk.init(
            dsn=dsn,
            traces_sample_rate=0.1,
            environment=os.getenv("APP_ENV", "development"),
            integrations=[FastApiIntegration()],
        )
    except BadDsn:
        # Do not block API startup because of a malformed DSN value.
        return
