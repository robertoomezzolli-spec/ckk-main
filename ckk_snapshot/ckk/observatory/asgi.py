"""ASGI entrypoint for the isolated Observatory sidecar."""

from .service import create_app

app = create_app()
