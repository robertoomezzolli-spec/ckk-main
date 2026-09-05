"""Internal HTTP API for the CKK knowledge adapter."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import hmac
import os
from pathlib import Path
import time
from typing import Any, Literal

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from .index import CKKIndex, GitMirror
from .publishing import PublicationError, ResearchPublisher
from .run_queue import CKKRunQueue


@dataclass(frozen=True)
class AdapterSettings:
    repository_url: str
    repository_ref: str
    cache_directory: str
    access_token: str
    refresh_seconds: int = 900
    run_queue_directory: str = "/jobs"
    run_artifact_directory: str = "/run-artifacts"
    publication_directory: str = "/publications"
    research_base_url: str = "https://kairos.206-189-55-212.sslip.io/research"

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
            run_queue_directory=os.getenv("CKK_RUN_QUEUE_DIRECTORY", "/jobs"),
            run_artifact_directory=os.getenv("CKK_RUN_ARTIFACT_DIRECTORY", "/run-artifacts"),
            publication_directory=os.getenv("CKK_PUBLICATION_DIRECTORY", "/publications"),
            research_base_url=os.getenv(
                "CKK_RESEARCH_BASE_URL", "https://kairos.206-189-55-212.sslip.io/research"
            ),
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


class ReadRequest(BaseModel):
    path: str = Field(min_length=1, max_length=500)
    ref: str | None = Field(default=None, max_length=200)


class SymbolRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    limit: int = Field(default=8, ge=1, le=20)


class RunRequest(BaseModel):
    seed: str = Field(min_length=1, max_length=128)
    operators: list[str] = Field(default_factory=list, max_length=16)
    controls: list[str] = Field(default_factory=lambda: ["structural_identity"], max_length=8)
    budgets: dict[str, Any] = Field(default_factory=dict)
    ref: str | None = Field(default=None, max_length=200)


class PublishRequest(BaseModel):
    run_id: str = Field(pattern=r"^[0-9a-f]{32}$")


def create_app(
    settings: AdapterSettings | None = None,
    index: CKKIndex | None = None,
    run_queue: CKKRunQueue | None = None,
) -> FastAPI:
    settings = settings or AdapterSettings.from_env()
    cache = Path(settings.cache_directory)
    index = index or CKKIndex(
        GitMirror(settings.repository_url, cache / "repository.git", settings.repository_ref),
        cache / "index.sqlite3",
    )
    run_queue = run_queue or CKKRunQueue(index.mirror, settings.run_queue_directory)
    publisher = ResearchPublisher(
        Path(settings.run_artifact_directory), Path(settings.publication_directory), settings.research_base_url
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
            "runner_isolation": "network_mode_none",
            "runner_queue_configured": bool(settings.run_queue_directory),
            "publisher_configured": bool(settings.publication_directory and settings.research_base_url),
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

    @app.post("/v1/read")
    async def read(request: ReadRequest, authorization: str = Header(default="")):
        authorize(authorization)
        try:
            return await asyncio.to_thread(index.mirror.read_path, request.path, request.ref)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="repository path not found") from exc

    @app.post("/v1/symbol")
    async def symbol(request: SymbolRequest, authorization: str = Header(default="")):
        authorize(authorization)
        return await asyncio.to_thread(index.symbol, request.name, request.limit)

    @app.post("/v1/run")
    async def run(request: RunRequest, authorization: str = Header(default="")):
        authorize(authorization)
        result = await asyncio.to_thread(
            run_queue.run, request.seed, request.operators, request.controls, request.budgets, request.ref
        )
        if result.get("status") != "completed":
            raise HTTPException(status_code=422, detail={
                "error_type": result.get("error_type", "RunnerError"),
                "error": result.get("error", "sealed runner failed"),
                "run_id": result.get("run_id"),
                "commit_sha": result.get("commit_sha"),
            })
        return result

    @app.post("/v1/publish")
    async def publish(request: PublishRequest, authorization: str = Header(default="")):
        authorize(authorization)
        try:
            return await asyncio.to_thread(publisher.publish, request.run_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="sealed run artifact not found") from exc
        except PublicationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    return app
