"""Internal HTTP API for the CKK knowledge adapter."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import hmac
import os
from pathlib import Path
import time
from typing import Literal

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from .index import CKKIndex, GitMirror


@dataclass(frozen=True)
class AdapterSettings:
    repository_url: str
    repository_ref: str
    cache_directory: str
    access_token: str
    refresh_seconds: int = 900

    @classmethod
    def from_env(cls) -> "AdapterSettings":
        token = os.getenv("CKK_ADAPTER_TOKEN", "")
        if len(token) < 32:
            raise RuntimeError("CKK_ADAPTER_TOKEN must contain at least 32 characters")
        return cls(
            repository_url=os.getenv("CKK_REPOSITORY_URL", "https://github.com/robertoomezzolli-spec/ckk.git"),
            repository_ref=os.getenv("CKK_REPOSITORY_REF", "main"),
            cache_directory=os.getenv("CKK_CACHE_DIRECTORY", "/cache"),
            access_token=token,
            refresh_seconds=max(60, int(os.getenv("CKK_REFRESH_SECONDS", "900"))),
        )


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=8, ge=1, le=20)
    mode: Literal["hybrid", "exact", "semantic", "symbol", "filename"] = "hybrid"


class HistoryRequest(BaseModel):
    term: str = Field(min_length=1, max_length=128)
    limit: int = Field(default=20, ge=1, le=50)


class DiffRequest(BaseModel):
    base_ref: str = Field(min_length=1, max_length=200)
    target_ref: str = Field(min_length=1, max_length=200)


def create_app(settings: AdapterSettings | None = None, index: CKKIndex | None = None) -> FastAPI:
    settings = settings or AdapterSettings.from_env()
    cache = Path(settings.cache_directory)
    index = index or CKKIndex(
        GitMirror(settings.repository_url, cache / "repository.git", settings.repository_ref),
        cache / "index.sqlite3",
    )
    app = FastAPI(title="CKK Knowledge Adapter", docs_url=None, redoc_url=None, openapi_url=None)
    stop = asyncio.Event()
    state = {"last_refresh_error": None, "last_refresh_attempt": None}

    def authorize(authorization: str) -> None:
        expected = f"Bearer {settings.access_token}"
        if not hmac.compare_digest(authorization, expected):
            raise HTTPException(status_code=401, detail="unauthorized")

    def refresh() -> None:
        state["last_refresh_attempt"] = int(time.time())
        try:
            index.refresh()
            state["last_refresh_error"] = None
        except Exception as exc:
            state["last_refresh_error"] = type(exc).__name__
            if index.indexed_commit() is None:
                raise

    async def refresher() -> None:
        while not stop.is_set():
            await asyncio.sleep(settings.refresh_seconds)
            await asyncio.to_thread(refresh)

    @app.on_event("startup")
    async def startup() -> None:
        await asyncio.to_thread(refresh)
        app.state.refresher = asyncio.create_task(refresher())

    @app.on_event("shutdown")
    async def shutdown() -> None:
        stop.set()
        task = getattr(app.state, "refresher", None)
        if task is not None:
            task.cancel()

    @app.get("/healthz")
    async def healthz():
        try:
            status = index.status()
        except Exception:
            raise HTTPException(status_code=503, detail="index unavailable")
        return {
            **status,
            "read_only_source": True,
            "last_refresh_attempt": state["last_refresh_attempt"],
            "last_refresh_error": state["last_refresh_error"],
        }

    @app.post("/v1/search")
    async def search(request: SearchRequest, authorization: str = Header(default="")):
        authorize(authorization)
        return await asyncio.to_thread(index.search, request.query, request.limit, request.mode)

    @app.post("/v1/retrieve")
    async def retrieve(request: SearchRequest, authorization: str = Header(default="")):
        authorize(authorization)
        return await asyncio.to_thread(index.retrieve, request.query, request.limit)

    @app.post("/v1/history")
    async def history(request: HistoryRequest, authorization: str = Header(default="")):
        authorize(authorization)
        return await asyncio.to_thread(index.history, request.term, request.limit)

    @app.post("/v1/diff")
    async def diff(request: DiffRequest, authorization: str = Header(default="")):
        authorize(authorization)
        return await asyncio.to_thread(index.diff, request.base_ref, request.target_ref)

    return app
