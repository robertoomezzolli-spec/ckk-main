"""Disk-backed, code-aware index over an immutable Git commit.

The adapter owns a read-only mirror of CKK and an independently rebuildable
SQLite index.  Retrieved text is evidence, never an assertion of truth.
"""

from __future__ import annotations

from array import array
import ast
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import sqlite3
import subprocess
import tempfile
import threading
from typing import Any, Iterable


TEXT_SUFFIXES = {
    ".py", ".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx", ".md", ".rst",
    ".txt", ".json", ".jsonl", ".yaml", ".yml", ".toml", ".ini", ".cfg",
    ".sql", ".csv", ".html", ".css", ".sh",
}
SOURCE_SUFFIXES = {".py", ".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx", ".sql", ".sh"}
VECTOR_SIZE = 256
MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_QUERY_LENGTH = 500
MAX_EXCERPT_CHARS = 6000
_SAFE_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/@{}^~:+-]{0,199}$")
_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]{1,127}")
_WORD = re.compile(r"[A-Za-z0-9_]{2,}")
_JS_SYMBOL = re.compile(
    r"^\s*(?:export\s+)?(?:async\s+)?(?:function|class)\s+([A-Za-z_$][\w$]*)|"
    r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=",
    re.MULTILINE,
)
_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_git(repo: Path | None, *args: str, timeout: int = 180) -> str:
    command = ["git"]
    if repo is not None:
        command.extend(["-C", str(repo)])
    command.extend(args)
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_NOSYSTEM": "1"}
    result = subprocess.run(command, capture_output=True, check=False, env=env, timeout=timeout)
    if result.returncode:
        error = result.stderr.decode("utf-8", "replace").strip()
        raise RuntimeError(f"read-only git operation failed ({args[0]}): {error[:500]}")
    return result.stdout.decode("utf-8", "replace")


def _valid_ref(value: str) -> str:
    value = value.strip()
    if not _SAFE_REF.fullmatch(value) or value.startswith("-") or ".." in value:
        raise ValueError("invalid Git ref")
    return value


@dataclass(frozen=True)
class GitTreeItem:
    path: str
    blob_sha: str
    size: int


class GitMirror:
    """A fetch-only Git mirror with an explicitly disabled push URL."""

    def __init__(self, repository_url: str, path: str | Path, default_ref: str = "main"):
        if not repository_url.startswith("https://github.com/") or not repository_url.endswith(".git"):
            raise ValueError("CKK repository must be an HTTPS GitHub .git URL")
        self.repository_url = repository_url
        self.path = Path(path)
        self.default_ref = _valid_ref(default_ref)

    def refresh(self) -> str:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            _run_git(None, "clone", "--mirror", self.repository_url, str(self.path), timeout=300)
        elif not (self.path / "HEAD").exists():
            raise RuntimeError("cache path exists but is not a Git mirror")
        actual = _run_git(self.path, "remote", "get-url", "origin").strip()
        if actual != self.repository_url:
            raise RuntimeError("cached mirror origin does not match configured CKK repository")
        _run_git(self.path, "remote", "set-url", "--push", "origin", "disabled://read-only")
        _run_git(self.path, "fetch", "--prune", "--tags", "origin", timeout=300)
        return self.resolve(self.default_ref)

    def resolve(self, ref: str | None = None) -> str:
        safe = _valid_ref(ref or self.default_ref)
        value = _run_git(self.path, "rev-parse", "--verify", f"{safe}^{{commit}}").strip()
        if not re.fullmatch(r"[0-9a-f]{40}", value):
            raise RuntimeError("Git did not return a full commit SHA")
        return value

    def tree(self, commit_sha: str) -> Iterable[GitTreeItem]:
        commit_sha = self.resolve(commit_sha)
        output = _run_git(self.path, "ls-tree", "-r", "-z", "--long", commit_sha)
        for raw in output.split("\0"):
            if not raw or "\t" not in raw:
                continue
            metadata, path = raw.split("\t", 1)
            fields = metadata.split()
            if len(fields) != 4 or fields[1] != "blob":
                continue
            size = int(fields[3]) if fields[3].isdigit() else 0
            yield GitTreeItem(path, fields[2], size)

    def blob(self, blob_sha: str) -> bytes:
        if not re.fullmatch(r"[0-9a-f]{40}", blob_sha):
            raise ValueError("invalid blob SHA")
        command = ["git", "-C", str(self.path), "cat-file", "blob", blob_sha]
        env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_NOSYSTEM": "1"}
        result = subprocess.run(command, capture_output=True, check=False, env=env, timeout=60)
        if result.returncode:
            raise RuntimeError("unable to read Git blob")
        return result.stdout

    def history(self, term: str, limit: int = 20) -> list[dict[str, Any]]:
        term = term.strip()[:128]
        if not term:
            return []
        marker = "CKK-COMMIT-BOUNDARY"
        output = _run_git(
            self.path, "log", "--all", "--max-count=200",
            f"--format={marker}%n%H%n%cI%n%s", f"-G{re.escape(term)}", "--name-only", "--",
        )
        records: list[dict[str, Any]] = []
        for section in output.split(marker)[1:]:
            lines = section.strip().splitlines()
            if len(lines) < 3:
                continue
            sha, authored_at, subject = lines[:3]
            paths = [line for line in lines[3:] if line.strip()]
            for path in paths or ["(repository history)"]:
                records.append({
                    "repository": self.repository_url.removesuffix(".git"),
                    "commit_sha": sha,
                    "path": path,
                    "authored_at": authored_at,
                    "subject": subject,
                    "term": term,
                    "source_kind": "commit_history",
                    "evidence_labels": ["commit_history"],
                    "truth_status": "external_evidence_unverified",
                    "belief_status": "not_committed",
                })
        if len(records) <= limit:
            selected = records
        elif limit == 1:
            selected = [records[-1]]
        else:
            selected = [*records[: limit - 1], records[-1]]
        for index, item in enumerate(selected):
            item["history_position"] = (
                "oldest_matching_change" if item is records[-1] else "recent_matching_change"
            )
        return selected

    def diff(self, base_ref: str, target_ref: str, maximum_chars: int = 24000) -> list[dict[str, Any]]:
        base = self.resolve(base_ref)
        target = self.resolve(target_ref)
        output = _run_git(self.path, "diff", "--no-ext-diff", "--unified=3", base, target, "--")
        items: list[dict[str, Any]] = []
        current_path = "(repository diff)"
        buffer: list[str] = []
        used = 0

        def flush() -> None:
            nonlocal used, buffer
            if not buffer or used >= maximum_chars:
                buffer = []
                return
            excerpt = "\n".join(buffer)[: maximum_chars - used]
            used += len(excerpt)
            labels = classify_source(current_path)[1]
            items.append({
                "repository": self.repository_url.removesuffix(".git"),
                "base_commit_sha": base,
                "commit_sha": target,
                "path": current_path,
                "source_kind": "commit_diff",
                "evidence_labels": sorted(set(labels + ["commit_diff"])),
                "excerpt": excerpt,
                "truth_status": "external_evidence_unverified",
                "belief_status": "not_committed",
            })
            buffer = []

        for line in output.splitlines():
            if line.startswith("diff --git "):
                flush()
                match = re.match(r"diff --git a/(.+?) b/(.+)$", line)
                current_path = match.group(2) if match else "(repository diff)"
            buffer.append(line)
        flush()
        return items


def classify_source(path: str) -> tuple[str, list[str]]:
    """Classify evidence by provenance, not by what its prose claims."""

    lower = path.lower()
    suffix = PurePosixPath(lower).suffix
    labels: set[str] = set()
    if suffix in SOURCE_SUFFIXES:
        labels.add("source_code")
    if lower.startswith("audit/"):
        labels.add("audit")
    if (
        lower in {"site/public/data/run34.json", "site/public/data/science-preview.json"}
        or lower.endswith(".snapshot.json")
        or "/snapshots/" in lower
    ):
        labels.add("snapshot")
    if suffix in {".md", ".rst", ".txt"} or lower == "readme.md" or lower.startswith("docs/"):
        labels.add("documentation")
    if "hypothesis" in lower or "hypotheses" in lower:
        labels.add("hypothesis")
    if (
        (lower.startswith("audit/") and suffix in {".json", ".csv"})
        or lower.startswith("site/public/data/")
        or "/generated/" in lower
        or "/results/" in lower
    ):
        labels.add("generated_result")
    if not labels:
        labels.add("documentation" if suffix in {".md", ".txt"} else "repository_file")
    precedence = ("snapshot", "generated_result", "audit", "source_code", "hypothesis", "documentation", "repository_file")
    primary = next(item for item in precedence if item in labels)
    return primary, sorted(labels)


def _identifier_parts(value: str) -> list[str]:
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", value).replace("_", "-")
    return [part.lower() for part in re.split(r"[^A-Za-z0-9]+", spaced) if len(part) > 1]


_SEMANTIC_GROUPS = (
    ("limit", "cutoff", "bound", "maximum", "max", "cap", "maxdim"),
    ("dimension", "dim", "dimensional", "maxdim"),
    ("history", "origin", "introduced", "changed", "commit", "provenance", "backtrace"),
    ("close", "closure", "closing"),
    ("wind", "winding", "integer"),
    ("snapshot", "sealed", "historical", "run34"),
    ("code", "implementation", "grammar", "operator", "function", "symbol"),
    ("evidence", "support", "source", "audit"),
)


def _semantic_expansion(tokens: Iterable[str]) -> list[str]:
    values = set(tokens)
    for group in _SEMANTIC_GROUPS:
        if values.intersection(group):
            values.update(group)
    return sorted(values)


def _features(text: str, query: bool = False) -> list[str]:
    raw = [match.group(0).lower() for match in _WORD.finditer(text[:200_000])]
    parts: list[str] = []
    for token in raw:
        parts.extend(_identifier_parts(token) or [token])
        if len(token) >= 4:
            parts.extend(f"tri:{token[index:index + 3]}" for index in range(len(token) - 2))
    # The same fixed expansion is applied to documents and queries.  This keeps
    # similarity symmetric and avoids using a remote embedding/model service.
    return _semantic_expansion(parts)


def _vector(text: str, query: bool = False) -> bytes:
    counts = Counter(_features(text, query=query))
    values = [0.0] * VECTOR_SIZE
    for feature, count in counts.items():
        digest = hashlib.blake2s(feature.encode(), digest_size=4).digest()
        raw = int.from_bytes(digest, "little")
        index = raw % VECTOR_SIZE
        sign = -1.0 if raw & 0x80000000 else 1.0
        values[index] += sign * (1.0 + math.log(count))
    norm = math.sqrt(sum(value * value for value in values)) or 1.0
    return array("f", (value / norm for value in values)).tobytes()


def _cosine(left: bytes, right: bytes) -> float:
    a, b = array("f"), array("f")
    a.frombytes(left)
    b.frombytes(right)
    return sum(x * y for x, y in zip(a, b))


def _symbols(path: str, content: str) -> list[tuple[str, str, int, int]]:
    suffix = PurePosixPath(path).suffix.lower()
    found: list[tuple[str, str, int, int]] = []
    if suffix == ".py":
        try:
            tree = ast.parse(content)
        except SyntaxError:
            tree = None
        if tree:
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    found.append((node.name, type(node).__name__, node.lineno, getattr(node, "end_lineno", node.lineno)))
                elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                    for target in targets:
                        if isinstance(target, ast.Name):
                            found.append((target.id, type(node).__name__, node.lineno, getattr(node, "end_lineno", node.lineno)))
    elif suffix in {".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx"}:
        for match in _JS_SYMBOL.finditer(content):
            name = match.group(1) or match.group(2)
            line = content.count("\n", 0, match.start()) + 1
            found.append((name, "javascript_symbol", line, line))
    elif suffix in {".md", ".rst", ".txt"}:
        for match in _HEADING.finditer(content):
            line = content.count("\n", 0, match.start()) + 1
            found.append((match.group(2).strip(), "heading", line, line))
    return found


def _chunks(content: str, window_lines: int = 80, overlap_lines: int = 12) -> Iterable[tuple[int, int, str]]:
    lines = content.splitlines()
    if not lines:
        return
    if len(lines) == 1 and len(lines[0]) > MAX_EXCERPT_CHARS:
        step = MAX_EXCERPT_CHARS - 600
        for start in range(0, len(lines[0]), step):
            yield 1, 1, lines[0][start : start + MAX_EXCERPT_CHARS]
        return
    step = max(1, window_lines - overlap_lines)
    for start in range(0, len(lines), step):
        end = min(len(lines), start + window_lines)
        excerpt = "\n".join(lines[start:end])
        if excerpt.strip():
            yield start + 1, end, excerpt[:MAX_EXCERPT_CHARS]
        if end == len(lines):
            break


class CKKIndex:
    SCHEMA_VERSION = "1"

    def __init__(self, mirror: GitMirror, database_path: str | Path):
        self.mirror = mirror
        self.database_path = Path(database_path)
        self._lock = threading.RLock()

    def indexed_commit(self) -> str | None:
        if not self.database_path.exists():
            return None
        try:
            with self._connect() as db:
                row = db.execute("SELECT value FROM metadata WHERE key='commit_sha'").fetchone()
                return str(row[0]) if row else None
        except sqlite3.Error:
            return None

    def refresh(self) -> dict[str, Any]:
        commit = self.mirror.refresh()
        if self.indexed_commit() != commit:
            self.rebuild(commit)
        return self.status()

    def rebuild(self, commit_sha: str) -> None:
        commit_sha = self.mirror.resolve(commit_sha)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary_name = tempfile.mkstemp(prefix="ckk-index-", suffix=".sqlite3", dir=self.database_path.parent)
        os.close(handle)
        temporary = Path(temporary_name)
        documents = chunks = symbols = 0
        try:
            db = sqlite3.connect(temporary)
            with db:
                db.executescript(
                    """
                    PRAGMA journal_mode=DELETE;
                    PRAGMA synchronous=FULL;
                    CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                    CREATE TABLE documents (
                      document_id INTEGER PRIMARY KEY, path TEXT NOT NULL UNIQUE, commit_sha TEXT NOT NULL,
                      blob_sha TEXT NOT NULL, source_kind TEXT NOT NULL, evidence_labels TEXT NOT NULL,
                      content_sha256 TEXT NOT NULL
                    );
                    CREATE TABLE chunks (
                      chunk_id INTEGER PRIMARY KEY, document_id INTEGER NOT NULL REFERENCES documents(document_id),
                      start_line INTEGER NOT NULL, end_line INTEGER NOT NULL, symbols TEXT NOT NULL,
                      content TEXT NOT NULL, vector BLOB NOT NULL
                    );
                    CREATE TABLE symbol_index (
                      symbol TEXT NOT NULL, symbol_kind TEXT NOT NULL, line INTEGER NOT NULL,
                      chunk_id INTEGER NOT NULL REFERENCES chunks(chunk_id)
                    );
                    CREATE INDEX symbol_name_idx ON symbol_index(symbol COLLATE NOCASE);
                    CREATE INDEX chunks_document_idx ON chunks(document_id);
                    CREATE VIRTUAL TABLE chunk_fts USING fts5(chunk_id UNINDEXED, path, symbols, content, tokenize='unicode61 tokenchars _');
                    """
                )
                for item in self.mirror.tree(commit_sha):
                    suffix = PurePosixPath(item.path).suffix.lower()
                    if suffix not in TEXT_SUFFIXES or item.size > MAX_FILE_BYTES:
                        continue
                    if PurePosixPath(item.path).name in {"package-lock.json", "yarn.lock", "pnpm-lock.yaml"}:
                        continue
                    raw = self.mirror.blob(item.blob_sha)
                    if b"\0" in raw[:8192]:
                        continue
                    content = raw.decode("utf-8", "replace")
                    primary, labels = classify_source(item.path)
                    cursor = db.execute(
                        "INSERT INTO documents(path,commit_sha,blob_sha,source_kind,evidence_labels,content_sha256) "
                        "VALUES (?,?,?,?,?,?)",
                        (item.path, commit_sha, item.blob_sha, primary, json.dumps(labels), hashlib.sha256(raw).hexdigest()),
                    )
                    document_id = int(cursor.lastrowid)
                    documents += 1
                    definitions = _symbols(item.path, content)
                    for start, end, excerpt in _chunks(content):
                        names = sorted({name for name, _kind, line, _end in definitions if start <= line <= end})
                        cursor = db.execute(
                            "INSERT INTO chunks(document_id,start_line,end_line,symbols,content,vector) VALUES (?,?,?,?,?,?)",
                            (document_id, start, end, json.dumps(names), excerpt, _vector(excerpt)),
                        )
                        chunk_id = int(cursor.lastrowid)
                        db.execute(
                            "INSERT INTO chunk_fts(chunk_id,path,symbols,content) VALUES (?,?,?,?)",
                            (chunk_id, item.path, " ".join(names), excerpt),
                        )
                        for name, kind, line, _definition_end in definitions:
                            if start <= line <= end:
                                db.execute(
                                    "INSERT INTO symbol_index(symbol,symbol_kind,line,chunk_id) VALUES (?,?,?,?)",
                                    (name, kind, line, chunk_id),
                                )
                                symbols += 1
                        chunks += 1
                metadata = {
                    "schema_version": self.SCHEMA_VERSION,
                    "repository": self.mirror.repository_url.removesuffix(".git"),
                    "ref": self.mirror.default_ref,
                    "commit_sha": commit_sha,
                    "indexed_at": _utc_now(),
                    "documents": str(documents),
                    "chunks": str(chunks),
                    "symbols": str(symbols),
                }
                db.executemany("INSERT INTO metadata(key,value) VALUES (?,?)", metadata.items())
                db.execute("PRAGMA optimize")
            db.close()
            os.replace(temporary, self.database_path)
        finally:
            temporary.unlink(missing_ok=True)

    def status(self) -> dict[str, Any]:
        with self._lock, self._connect() as db:
            values = {str(row[0]): str(row[1]) for row in db.execute("SELECT key,value FROM metadata")}
        return {
            "status": "ok",
            **values,
            "documents": int(values.get("documents", 0)),
            "chunks": int(values.get("chunks", 0)),
            "symbols": int(values.get("symbols", 0)),
        }

    def search(self, query: str, limit: int = 8, mode: str = "hybrid") -> dict[str, Any]:
        query = query.strip()[:MAX_QUERY_LENGTH]
        if not query:
            raise ValueError("query is required")
        limit = max(1, min(int(limit), 20))
        if mode not in {"hybrid", "exact", "semantic", "symbol", "filename"}:
            raise ValueError("unsupported search mode")
        scores: dict[int, float] = {}
        methods: dict[int, set[str]] = {}

        def add(chunk_id: int, score: float, method: str) -> None:
            scores[chunk_id] = scores.get(chunk_id, 0.0) + score
            methods.setdefault(chunk_id, set()).add(method)

        tokens = list(dict.fromkeys(_features(query, query=True)))[:40]
        symbol_queries = [item for item in _IDENTIFIER.findall(query) if item.startswith("op_")]
        lowered_query = query.lower()
        with self._lock, self._connect() as db:
            if mode == "hybrid" and ("snapshot" in lowered_query or re.search(r"run[- ]?34", lowered_query)):
                for row in db.execute(
                    "SELECT c.chunk_id FROM chunks c JOIN documents d ON d.document_id=c.document_id "
                    "WHERE d.source_kind='snapshot' LIMIT 120"
                ):
                    add(int(row[0]), 20.0, "evidence_class")
                for row in db.execute(
                    "SELECT c.chunk_id FROM chunks c JOIN documents d ON d.document_id=c.document_id "
                    "WHERE lower(d.path) LIKE '%run34%' LIMIT 120"
                ):
                    add(int(row[0]), 5.0, "run34_path")
            if mode == "hybrid" and ("grammar" in lowered_query or "operator" in lowered_query):
                for row in db.execute(
                    "SELECT c.chunk_id FROM chunks c JOIN documents d ON d.document_id=c.document_id "
                    "WHERE lower(d.path) LIKE '%grammar.%' LIMIT 60"
                ):
                    add(int(row[0]), 8.0, "code_structure")
            if mode in {"hybrid", "symbol"}:
                for symbol in symbol_queries or _IDENTIFIER.findall(query)[:8]:
                    for row in db.execute(
                        "SELECT chunk_id FROM symbol_index WHERE symbol=? COLLATE NOCASE LIMIT 20", (symbol,)
                    ):
                        add(int(row[0]), 12.0, "exact_symbol")
            if mode in {"hybrid", "filename"}:
                filename = PurePosixPath(query.strip()).name.lower()
                if "." in filename:
                    for row in db.execute(
                        "SELECT c.chunk_id FROM chunks c JOIN documents d ON d.document_id=c.document_id "
                        "WHERE lower(d.path)=? OR lower(d.path) LIKE ? LIMIT 60",
                        (filename, f"%/{filename}"),
                    ):
                        add(int(row[0]), 14.0, "exact_filename")
                for word in _IDENTIFIER.findall(query)[:12]:
                    for row in db.execute(
                        "SELECT c.chunk_id FROM chunks c JOIN documents d ON d.document_id=c.document_id "
                        "WHERE lower(d.path) LIKE ? LIMIT 30", (f"%{word.lower()}%",)
                    ):
                        add(int(row[0]), 5.0, "filename")
            if mode in {"hybrid", "exact"}:
                phrases = symbol_queries or [query]
                for phrase in phrases:
                    for row in db.execute(
                        "SELECT chunk_id FROM chunks WHERE instr(lower(content), lower(?)) > 0 LIMIT 60", (phrase,)
                    ):
                        add(int(row[0]), 8.0, "exact_text")
            if mode in {"hybrid", "exact", "semantic"} and tokens:
                fts_query = " OR ".join(f'"{token.replace(chr(34), "")}"' for token in tokens if not token.startswith("tri:"))
                if fts_query:
                    try:
                        for row in db.execute(
                            "SELECT CAST(chunk_id AS INTEGER), bm25(chunk_fts) FROM chunk_fts WHERE chunk_fts MATCH ? LIMIT 120",
                            (fts_query,),
                        ):
                            add(int(row[0]), max(0.1, 3.0 + min(5.0, -float(row[1]))), "lexical_fts")
                    except sqlite3.OperationalError:
                        pass
            if mode in {"hybrid", "semantic"}:
                query_vector = _vector(query, query=True)
                semantic: list[tuple[float, int]] = []
                for row in db.execute("SELECT chunk_id,vector FROM chunks"):
                    similarity = _cosine(query_vector, bytes(row[1]))
                    if similarity > 0.08:
                        semantic.append((similarity, int(row[0])))
                for similarity, chunk_id in sorted(semantic, reverse=True)[:80]:
                    add(chunk_id, similarity * 5.0, "semantic_vector")
            # Rank all matching chunk IDs before path-level de-duplication. A
            # large JSON snapshot may contribute hundreds of adjacent chunks;
            # truncating first would crowd distinct source classes out.
            ranked = sorted(scores, key=lambda item: (-scores[item], item))
            items: list[dict[str, Any]] = []
            seen_paths: set[str] = set()
            for chunk_id in ranked:
                item = self._result(db, chunk_id, scores[chunk_id], methods[chunk_id])
                if item["path"] in seen_paths:
                    continue
                seen_paths.add(item["path"])
                items.append(item)
                if len(items) >= limit:
                    break
            metadata = {str(row[0]): str(row[1]) for row in db.execute("SELECT key,value FROM metadata")}
        return {
            "query": query,
            "mode": mode,
            "repository": metadata["repository"],
            "ref": metadata["ref"],
            "commit_sha": metadata["commit_sha"],
            "items": items,
        }

    def history(self, term: str, limit: int = 20) -> dict[str, Any]:
        status = self.status()
        return {
            "term": term[:128],
            "repository": status["repository"],
            "ref": status["ref"],
            "commit_sha": status["commit_sha"],
            "items": self.mirror.history(term, limit),
        }

    def diff(self, base_ref: str, target_ref: str) -> dict[str, Any]:
        items = self.mirror.diff(base_ref, target_ref)
        return {
            "repository": self.mirror.repository_url.removesuffix(".git"),
            "base_commit_sha": self.mirror.resolve(base_ref),
            "commit_sha": self.mirror.resolve(target_ref),
            "items": items,
        }

    def retrieve(self, query: str, limit: int = 8) -> dict[str, Any]:
        result = self.search(query, limit=limit, mode="hybrid")
        lowered = query.lower()
        history_terms = re.findall(r"\b[A-Z][A-Z0-9_]{2,}\b|\bop_[a-z0-9_]+\b", query)
        if any(word in lowered for word in ("history", "origin", "introduced", "changed", "backtrace", "where does")):
            term = history_terms[0] if history_terms else ""
            if term:
                result["history"] = self.mirror.history(term, min(limit, 10))
        refs = re.findall(r"(?<![0-9a-f])[0-9a-f]{7,40}(?![0-9a-f])", lowered)
        if len(refs) >= 2 and any(word in lowered for word in ("diff", "changed", "between", "compare")):
            result["diff"] = self.mirror.diff(refs[0], refs[1])
        return result

    def _connect(self) -> sqlite3.Connection:
        uri = f"file:{self.database_path}?mode=ro" if self.database_path.exists() else str(self.database_path)
        db = sqlite3.connect(uri, uri=self.database_path.exists(), timeout=30)
        db.row_factory = sqlite3.Row
        return db

    def _result(self, db: sqlite3.Connection, chunk_id: int, score: float, methods: set[str]) -> dict[str, Any]:
        row = db.execute(
            "SELECT c.chunk_id,c.start_line,c.end_line,c.symbols,c.content,d.path,d.commit_sha,d.blob_sha,"
            "d.source_kind,d.evidence_labels,d.content_sha256 FROM chunks c "
            "JOIN documents d ON d.document_id=c.document_id WHERE c.chunk_id=?", (chunk_id,)
        ).fetchone()
        if row is None:
            raise RuntimeError("index row disappeared")
        return {
            "repository": self.mirror.repository_url.removesuffix(".git"),
            "ref": self.mirror.default_ref,
            "commit_sha": row["commit_sha"],
            "blob_sha": row["blob_sha"],
            "path": row["path"],
            "start_line": int(row["start_line"]),
            "end_line": int(row["end_line"]),
            "symbols": json.loads(row["symbols"]),
            "source_kind": row["source_kind"],
            "evidence_labels": json.loads(row["evidence_labels"]),
            "content_sha256": row["content_sha256"],
            "retrieval_methods": sorted(methods),
            "score": round(score, 6),
            "excerpt": row["content"],
            "truth_status": "external_evidence_unverified",
            "belief_status": "not_committed",
        }
