"""Production ASGI entrypoint. Environment validation happens at boot."""

from .host import create_app

app = create_app()
