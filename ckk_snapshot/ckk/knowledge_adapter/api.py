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
from .experiment_ops import ExperimentOperations, ExperimentSettings
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
    experiment_enabled: bool = False
    experiment_repository_url: str = "https://github.com/robertoomezzolli-spec/ckk-main.git"
    experiment_branch: str = "experiment/solar-system-provenance-cascade"
    experiment_target_commit: str = "5faf926d6cc324e08c32649e1b92cf57f3c56cb3"
    experiment_cache_directory: str = "/experiment-cache"
    experiment_control_directory: str = "/experiment-control"
    experiment_artifact_directory: str = "/experiment-artifacts"
    experiment_manifest_path: str = "/app/sealed/fresh_seed_closure_plateau_v2_execution_manifest.json"

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
            experiment_enabled=os.getenv("CKK_EXPERIMENT_ENABLED", "false").lower() in {"1", "true", "yes"},
            experiment_repository_url=os.getenv(
                "CKK_EXPERIMENT_REPOSITORY_URL", "https://github.com/robertoomezzolli-spec/ckk-main.git"
            ),
            experiment_branch=os.getenv(
                "CKK_EXPERIMENT_BRANCH", "experiment/solar-system-provenance-cascade"
            ),
            experiment_target_commit=os.getenv(
                "CKK_EXPERIMENT_TARGET_COMMIT", "5faf926d6cc324e08c32649e1b92cf57f3c56cb3"
            ),
            experiment_cache_directory=os.getenv("CKK_EXPERIMENT_CACHE_DIRECTORY", "/experiment-cache"),
            experiment_control_directory=os.getenv("CKK_EXPERIMENT_CONTROL_DIRECTORY", "/experiment-control"),
            experiment_artifact_directory=os.getenv("CKK_EXPERIMENT_ARTIFACT_DIRECTORY", "/experiment-artifacts"),
            experiment_manifest_path=os.getenv(
                "CKK_EXPERIMENT_MANIFEST_PATH",
                "/app/sealed/fresh_seed_closure_plateau_v2_execution_manifest.json",
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


class RepoOperationRequest(BaseModel):
    operation: Literal["sync", "checkout", "status", "read", "diff", "manifest"]
    path: str | None = Field(default=None, max_length=500)
    ref: str | None = Field(default=None, max_length=200)
    base_ref: str | None = Field(default=None, max_length=200)
    target_ref: str | None = Field(default=None, max_length=200)


class ProcessRunRequest(BaseModel):
    task: Literal["supervisor_smoke", "equivalence_validation", "fresh_seed_closure_plateau_v2"]
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ProcessJobRequest(BaseModel):
    job_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")


class ProcessStopRequest(BaseModel):
    job_id: str = Field(pattern=r"^[0-9a-f]{32}$")


class FileReadRequest(BaseModel):
    path: str = Field(min_length=34, max_length=800)
    offset: int = Field(default=0, ge=0)
    maximum_chars: int = Field(default=24000, ge=1, le=32000)


class FileHashRequest(BaseModel):
    path: str = Field(min_length=34, max_length=800)


def create_app(
    settings: AdapterSettings | None = None,
    index: CKKIndex | None = None,
    run_queue: CKKRunQueue | None = None,
    experiment_ops: ExperimentOperations | None = None,
) -> FastAPI:
    settings = settings or AdapterSettings.from_env()
    cache = Path(settings.cache_directory)
    index = index or CKKIndex(
        GitMirror(settings.repository_url, cache / "repository.git", settings.repository_ref),
        cache / "index.sqlite3",
    )
    run_queue = run_queue or CKKRunQueue(index.mirror, settings.run_queue_directory)
    if experiment_ops is None and settings.experiment_enabled:
        experiment_ops = ExperimentOperations(ExperimentSettings(
            repository_url=settings.experiment_repository_url,
            branch=settings.experiment_branch,
            target_commit=settings.experiment_target_commit,
            cache_directory=settings.experiment_cache_directory,
            control_directory=settings.experiment_control_directory,
            artifact_directory=settings.experiment_artifact_directory,
            manifest_path=settings.experiment_manifest_path,
        ))
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

    def require_experiment() -> ExperimentOperations:
        if experiment_ops is None:
            raise HTTPException(status_code=503, detail="frozen experiment operations are not configured")
        return experiment_ops

    async def experiment_call(function, *args, **kwargs):
        try:
            return await asyncio.to_thread(function, *args, **kwargs)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

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
        if experiment_ops is not None:
            await asyncio.to_thread(experiment_ops.refresh)
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
            "frozen_experiment": experiment_ops.health() if experiment_ops is not None else {"configured": False},
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

    @app.post("/v1/experiment/repo")
    async def experiment_repo(request: RepoOperationRequest, authorization: str = Header(default="")):
        authorize(authorization)
        operations = require_experiment()
        return await experiment_call(
            operations.repo,
            request.operation,
            path=request.path,
            ref=request.ref,
            base_ref=request.base_ref,
            target_ref=request.target_ref,
        )

    @app.post("/v1/experiment/process/run")
    async def experiment_process_run(request: ProcessRunRequest, authorization: str = Header(default="")):
        authorize(authorization)
        operations = require_experiment()
        return await experiment_call(operations.start, request.task, request.manifest_sha256)

    @app.post("/v1/experiment/process/status")
    async def experiment_process_status(request: ProcessJobRequest, authorization: str = Header(default="")):
        authorize(authorization)
        operations = require_experiment()
        return await experiment_call(operations.status, request.job_id)

    @app.post("/v1/experiment/process/stop")
    async def experiment_process_stop(request: ProcessStopRequest, authorization: str = Header(default="")):
        authorize(authorization)
        operations = require_experiment()
        return await experiment_call(operations.stop, request.job_id)

    @app.post("/v1/experiment/file/read")
    async def experiment_file_read(request: FileReadRequest, authorization: str = Header(default="")):
        authorize(authorization)
        operations = require_experiment()
        return await experiment_call(operations.file_read, request.path, request.offset, request.maximum_chars)

    @app.post("/v1/experiment/file/hash")
    async def experiment_file_hash(request: FileHashRequest, authorization: str = Header(default="")):
        authorize(authorization)
        operations = require_experiment()
        return await experiment_call(operations.file_hash, request.path)

    @app.post("/v1/experiment/system/metrics")
    async def experiment_system_metrics(request: ProcessJobRequest, authorization: str = Header(default="")):
        authorize(authorization)
        operations = require_experiment()
        return await experiment_call(operations.metrics, request.job_id)

    return app
