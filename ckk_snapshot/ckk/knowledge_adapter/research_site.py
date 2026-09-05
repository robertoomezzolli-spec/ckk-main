"""Read-only ASGI surface for generated CKK research publications."""

from __future__ import annotations

import os
from pathlib import Path
import re

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse


_RUN_ID = re.compile(r"^[0-9a-f]{32}$")
_ARTIFACTS = {
    "report.json": "application/json",
    "report.md": "text/markdown; charset=utf-8",
    "artifacts/request.json": "application/json",
    "artifacts/result.json": "application/json",
}


def create_research_site(directory: str | Path | None = None) -> FastAPI:
    root = Path(directory or os.getenv("CKK_PUBLICATION_DIRECTORY", "/publications"))
    app = FastAPI(title="KAIROS CKK Research", docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def security_headers(request, call_next):
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; style-src 'unsafe-inline'; img-src 'self'; "
            "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
        )
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Cache-Control"] = "public, max-age=60"
        return response

    @app.get("/healthz", include_in_schema=False)
    async def healthz():
        return {"status": "ok", "read_only": True, "publication_count": sum(1 for p in root.glob("*/report.json") if _RUN_ID.fullmatch(p.parent.name))}

    @app.get("/research", include_in_schema=False)
    async def research_redirect():
        return RedirectResponse("/research/", status_code=308)

    @app.get("/research/", response_class=HTMLResponse, include_in_schema=False)
    async def index_html():
        path = root / "index.html"
        if not path.is_file():
            raise HTTPException(status_code=404, detail="research index unavailable")
        return HTMLResponse(path.read_text(encoding="utf-8"))

    @app.get("/research/index.json", response_class=JSONResponse, include_in_schema=False)
    async def index_json():
        path = root / "index.json"
        if not path.is_file():
            raise HTTPException(status_code=404, detail="research index unavailable")
        return FileResponse(path, media_type="application/json")

    @app.get("/research/{run_id}", response_class=HTMLResponse, include_in_schema=False)
    async def experiment(run_id: str):
        if not _RUN_ID.fullmatch(run_id):
            raise HTTPException(status_code=404, detail="experiment not found")
        path = root / run_id / "index.html"
        if not path.is_file():
            raise HTTPException(status_code=404, detail="experiment not found")
        return HTMLResponse(path.read_text(encoding="utf-8"))

    @app.get("/research/{run_id}/{artifact:path}", include_in_schema=False)
    async def artifact(run_id: str, artifact: str):
        if not _RUN_ID.fullmatch(run_id) or artifact not in _ARTIFACTS:
            raise HTTPException(status_code=404, detail="artifact not found")
        path = root / run_id / artifact
        if not path.is_file():
            raise HTTPException(status_code=404, detail="artifact not found")
        return FileResponse(path, media_type=_ARTIFACTS[artifact], filename=path.name)

    return app
