"""Bounded, provenance-bearing ingestion for WhatsApp media.

The signed webhook admits only metadata. This module performs the separate
Meta download and content-extraction step before bytes become an observation.
No media operation is exposed as a general model capability.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field, replace
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
from typing import Any, Mapping, Protocol
from urllib import error, parse, request

from .runtime import Observation


META_MEDIA_HOST_SUFFIXES = (".facebook.com", ".fbcdn.net", ".fbsbx.com")
MEDIA_KINDS = frozenset({"message.document", "message.image"})


class MediaProcessingError(RuntimeError):
    """A content-free media failure safe to expose to cognition and logs."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class MediaEnvelope:
    media_id: str
    filename: str
    mime_type: str
    expected_sha256: str


@dataclass(frozen=True)
class MediaArtifact:
    artifact_id: str
    media_id: str
    filename: str
    mime_type: str
    size_bytes: int


@dataclass
class MediaVault:
    """Small in-memory quarantine retained for simulation and unit tests."""

    allowed_mime_types: frozenset[str] = frozenset(
        {
            "application/pdf",
            "text/plain",
            "image/jpeg",
            "image/png",
            "audio/ogg",
            "audio/mpeg",
            "audio/mp4",
        }
    )
    maximum_bytes: int = 25 * 1024 * 1024
    _content: dict[str, bytes] = field(default_factory=dict)

    def admit(self, envelope: MediaEnvelope, content: bytes) -> MediaArtifact:
        if envelope.mime_type not in self.allowed_mime_types:
            raise PermissionError("media type is not admitted")
        if not content or len(content) > self.maximum_bytes:
            raise ValueError("media size is outside admitted range")
        if envelope.expected_sha256 and not digest_matches(content, envelope.expected_sha256):
            raise ValueError("media hash does not match signed metadata")
        actual = hashlib.sha256(content).hexdigest()
        artifact_id = f"sha256:{actual}"
        self._content.setdefault(artifact_id, bytes(content))
        return MediaArtifact(
            artifact_id=artifact_id,
            media_id=envelope.media_id,
            filename=envelope.filename,
            mime_type=envelope.mime_type,
            size_bytes=len(content),
        )

    def read(self, artifact_id: str) -> bytes:
        return self._content[artifact_id]


def digest_matches(content: bytes, expected: str) -> bool:
    """Accept Meta's documented digest encodings without weakening equality."""

    expected = expected.strip()
    if not expected:
        return True
    digest = hashlib.sha256(content).digest()
    hexadecimal = digest.hex()
    encoded = base64.b64encode(digest).decode()
    return hmac.compare_digest(expected.lower(), hexadecimal) or hmac.compare_digest(
        expected.rstrip("="), encoded.rstrip("=")
    )


def _meta_https_url(url: str) -> bool:
    parsed = parse.urlparse(url)
    host = (parsed.hostname or "").lower()
    return (
        parsed.scheme == "https"
        and bool(host)
        and any(host == suffix[1:] or host.endswith(suffix) for suffix in META_MEDIA_HOST_SUFFIXES)
    )


class _MetaRedirectHandler(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        if not _meta_https_url(newurl):
            raise MediaProcessingError("media_redirect_rejected")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class MediaTransport(Protocol):
    def metadata(self, media_id: str, access_token: str, graph_api_version: str) -> Mapping[str, Any]: ...
    def download(self, url: str, access_token: str, maximum_bytes: int) -> tuple[bytes, str]: ...


@dataclass
class UrllibMediaTransport:
    timeout_seconds: float = 20.0

    def metadata(self, media_id: str, access_token: str, graph_api_version: str) -> Mapping[str, Any]:
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,256}", media_id):
            raise MediaProcessingError("invalid_media_id")
        url = f"https://graph.facebook.com/{graph_api_version}/{parse.quote(media_id, safe='')}"
        raw, _mime, _final = self._get(url, access_token, 64 * 1024)
        try:
            payload = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise MediaProcessingError("media_metadata_invalid_json") from exc
        if not isinstance(payload, Mapping) or not payload.get("url"):
            raise MediaProcessingError("media_metadata_missing_url")
        if payload.get("id") and str(payload["id"]) != media_id:
            raise MediaProcessingError("media_metadata_id_mismatch")
        return payload

    def download(self, url: str, access_token: str, maximum_bytes: int) -> tuple[bytes, str]:
        if not _meta_https_url(url):
            raise MediaProcessingError("media_url_rejected")
        raw, mime_type, final_url = self._get(url, access_token, maximum_bytes)
        if not _meta_https_url(final_url):
            raise MediaProcessingError("media_final_url_rejected")
        return raw, mime_type

    def _get(self, url: str, access_token: str, maximum_bytes: int) -> tuple[bytes, str, str]:
        if not access_token:
            raise MediaProcessingError("media_access_token_missing")
        req = request.Request(url, headers={"Authorization": f"Bearer {access_token}"}, method="GET")
        opener = request.build_opener(_MetaRedirectHandler())
        try:
            with opener.open(req, timeout=self.timeout_seconds) as response:
                declared = int(response.headers.get("Content-Length") or 0)
                if declared > maximum_bytes:
                    raise MediaProcessingError("media_too_large")
                chunks: list[bytes] = []
                size = 0
                while True:
                    chunk = response.read(min(64 * 1024, maximum_bytes + 1 - size))
                    if not chunk:
                        break
                    chunks.append(chunk)
                    size += len(chunk)
                    if size > maximum_bytes:
                        raise MediaProcessingError("media_too_large")
                return (
                    b"".join(chunks),
                    str(response.headers.get("Content-Type") or "").split(";", 1)[0],
                    response.geturl(),
                )
        except MediaProcessingError:
            raise
        except error.HTTPError as exc:
            raise MediaProcessingError(f"media_http_{int(exc.code)}") from exc
        except (error.URLError, TimeoutError) as exc:
            raise MediaProcessingError("media_transport_failed") from exc


class TextExtractor(Protocol):
    def extract(self, content: bytes, mime_type: str, filename: str) -> Mapping[str, Any]: ...


@dataclass
class PdfOcrTextExtractor:
    """Extract PDF text first and OCR only pages without usable text."""

    maximum_pages: int = 60
    maximum_text_bytes: int = 48 * 1024
    maximum_ocr_pages: int = 60
    minimum_direct_characters: int = 40
    render_dpi: int = 160
    command_timeout_seconds: float = 90.0
    ocr_languages: str = "deu+eng"
    child_memory_bytes: int = 512 * 1024 * 1024
    child_output_bytes: int = 128 * 1024 * 1024

    def extract(self, content: bytes, mime_type: str, filename: str) -> Mapping[str, Any]:
        if mime_type == "application/pdf":
            return self._extract_pdf(content, filename)
        if mime_type == "text/plain":
            text = content.decode("utf-8", errors="replace")
            text, truncated = self._bounded_text(text)
            return {
                "extracted_text": text,
                "page_count": 1,
                "processed_pages": 1,
                "text_pages": 1,
                "ocr_pages": 0,
                "methods": ["utf8_decode"],
                "truncated": truncated,
            }
        if mime_type in {"image/jpeg", "image/png"}:
            return self._extract_image(content, mime_type)
        raise MediaProcessingError("media_type_not_extractable")

    def _extract_pdf(self, content: bytes, filename: str) -> Mapping[str, Any]:
        if not content.startswith(b"%PDF-"):
            raise MediaProcessingError("pdf_signature_invalid")
        deadline = time.monotonic() + self.command_timeout_seconds
        with tempfile.TemporaryDirectory(prefix="kairos-media-") as directory:
            root = Path(directory)
            source = root / "document.pdf"
            source.write_bytes(content)
            os.chmod(source, 0o600)
            info = self._run(("pdfinfo", str(source)), timeout=self._remaining(deadline, 20.0))
            if info.returncode != 0:
                raise MediaProcessingError("pdf_info_failed")
            metadata = info.stdout.decode("utf-8", errors="replace")
            pages_match = re.search(r"(?m)^Pages:\s+(\d+)\s*$", metadata)
            if not pages_match:
                raise MediaProcessingError("pdf_page_count_missing")
            page_count = int(pages_match.group(1))
            if page_count < 1:
                raise MediaProcessingError("pdf_has_no_pages")
            if re.search(r"(?mi)^Encrypted:\s+yes", metadata):
                raise MediaProcessingError("pdf_is_encrypted")
            processed_pages = min(page_count, self.maximum_pages)
            direct = self._run(
                (
                    "pdftotext", "-layout", "-enc", "UTF-8", "-f", "1", "-l",
                    str(processed_pages), str(source), "-",
                ),
                timeout=self._remaining(deadline),
            )
            if direct.returncode != 0:
                raise MediaProcessingError("pdf_text_extraction_failed")
            page_texts = direct.stdout.decode("utf-8", errors="replace").split("\f")
            if page_texts and not page_texts[-1].strip():
                page_texts.pop()
            page_texts.extend([""] * max(0, processed_pages - len(page_texts)))
            rendered: list[str] = []
            text_pages = 0
            ocr_pages = 0
            methods: set[str] = set()
            for page_number in range(1, processed_pages + 1):
                page_text = page_texts[page_number - 1] if page_number <= len(page_texts) else ""
                direct_characters = len(re.sub(r"\s+", "", page_text))
                method = "pdftotext"
                if direct_characters < self.minimum_direct_characters and ocr_pages < self.maximum_ocr_pages:
                    page_text = self._ocr_pdf_page(source, root, page_number, deadline)
                    method = "tesseract_ocr"
                    ocr_pages += 1
                else:
                    text_pages += 1
                methods.add(method)
                rendered.append(f"[Page {page_number} | {method}]\n{page_text.strip()}")
            text, text_truncated = self._bounded_text("\n\n".join(rendered))
            return {
                "extracted_text": text,
                "page_count": page_count,
                "processed_pages": processed_pages,
                "text_pages": text_pages,
                "ocr_pages": ocr_pages,
                "methods": sorted(methods),
                "truncated": page_count > processed_pages or text_truncated,
                "original_filename": Path(filename).name[:255],
            }

    def _ocr_pdf_page(self, source: Path, root: Path, page_number: int, deadline: float) -> str:
        prefix = root / f"page-{page_number}"
        render = self._run(
            (
                "pdftoppm", "-png", "-singlefile", "-r", str(self.render_dpi),
                "-f", str(page_number), "-l", str(page_number), str(source), str(prefix),
            ),
            timeout=self._remaining(deadline),
        )
        image = prefix.with_suffix(".png")
        if render.returncode != 0 or not image.is_file():
            raise MediaProcessingError("pdf_page_render_failed")
        return self._tesseract(image, self._remaining(deadline))

    def _extract_image(self, content: bytes, mime_type: str) -> Mapping[str, Any]:
        suffix = ".jpg" if mime_type == "image/jpeg" else ".png"
        with tempfile.TemporaryDirectory(prefix="kairos-media-") as directory:
            image = Path(directory) / f"image{suffix}"
            image.write_bytes(content)
            os.chmod(image, 0o600)
            text, truncated = self._bounded_text(self._tesseract(image, self.command_timeout_seconds))
        return {
            "extracted_text": text,
            "page_count": 1,
            "processed_pages": 1,
            "text_pages": 0,
            "ocr_pages": 1,
            "methods": ["tesseract_ocr"],
            "truncated": truncated,
        }

    def _tesseract(self, image: Path, timeout: float) -> str:
        result = self._run(
            ("tesseract", str(image), "stdout", "-l", self.ocr_languages, "--psm", "3"),
            timeout=timeout,
        )
        if result.returncode != 0:
            raise MediaProcessingError("ocr_failed")
        return result.stdout.decode("utf-8", errors="replace")

    def _run(self, command: tuple[str, ...], *, timeout: float) -> subprocess.CompletedProcess[bytes]:
        environment = {**os.environ, "LC_ALL": "C", "OMP_THREAD_LIMIT": "1"}
        bounded_command = (
            "prlimit",
            f"--as={self.child_memory_bytes}",
            f"--cpu={max(1, int(self.command_timeout_seconds))}",
            f"--fsize={self.child_output_bytes}",
            "--",
            *command,
        )
        try:
            return subprocess.run(
                bounded_command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
                check=False,
                env=environment,
            )
        except FileNotFoundError as exc:
            raise MediaProcessingError("extractor_dependency_missing") from exc
        except subprocess.TimeoutExpired as exc:
            raise MediaProcessingError("extractor_timeout") from exc

    @staticmethod
    def _remaining(deadline: float, maximum: float | None = None) -> float:
        remaining = deadline - time.monotonic()
        if maximum is not None:
            remaining = min(remaining, maximum)
        if remaining <= 0:
            raise MediaProcessingError("extractor_timeout")
        return remaining

    def _bounded_text(self, value: str) -> tuple[str, bool]:
        raw = value.encode("utf-8")
        if len(raw) <= self.maximum_text_bytes:
            return value, False
        marker = b"\n[TRUNCATED AT DOCUMENT EXTRACTION BUDGET]"
        bounded = raw[: max(0, self.maximum_text_bytes - len(marker))].decode("utf-8", errors="ignore")
        return bounded + marker.decode(), True


@dataclass
class MediaObservationEnricher:
    access_token: str
    graph_api_version: str = "v23.0"
    maximum_bytes: int = 25 * 1024 * 1024
    transport: MediaTransport = field(default_factory=UrllibMediaTransport)
    extractor: TextExtractor = field(default_factory=PdfOcrTextExtractor)

    def enrich(self, observation: Observation) -> Observation:
        if observation.kind not in MEDIA_KINDS:
            return observation
        payload = dict(observation.payload)
        if payload.get("extraction_status") in {"extracted", "failed"}:
            return observation
        try:
            envelope = MediaEnvelope(
                media_id=str(payload.get("media_id") or ""),
                filename=str(payload.get("filename") or "media")[:255],
                mime_type=str(payload.get("mime_type") or "application/octet-stream").split(";", 1)[0],
                expected_sha256=str(payload.get("sha256") or ""),
            )
            metadata = self.transport.metadata(envelope.media_id, self.access_token, self.graph_api_version)
            declared_size = int(metadata.get("file_size") or 0)
            if declared_size > self.maximum_bytes:
                raise MediaProcessingError("media_too_large")
            remote_mime = str(metadata.get("mime_type") or envelope.mime_type).split(";", 1)[0]
            if (
                envelope.mime_type != "application/octet-stream"
                and remote_mime != "application/octet-stream"
                and remote_mime != envelope.mime_type
            ):
                raise MediaProcessingError("media_mime_mismatch")
            content, response_mime = self.transport.download(
                str(metadata["url"]), self.access_token, self.maximum_bytes
            )
            if not content:
                raise MediaProcessingError("media_empty")
            actual_mime = remote_mime if remote_mime != "application/octet-stream" else response_mime
            if actual_mime not in {"application/pdf", "text/plain", "image/jpeg", "image/png"}:
                raise MediaProcessingError("media_type_not_extractable")
            for expected in (envelope.expected_sha256, str(metadata.get("sha256") or "")):
                if expected and not digest_matches(content, expected):
                    raise MediaProcessingError("media_hash_mismatch")
            extraction = dict(self.extractor.extract(content, actual_mime, envelope.filename))
            payload.update(
                {
                    "extraction_status": "extracted",
                    "extracted_text": str(extraction.pop("extracted_text", "")),
                    "document_provenance": {
                        "classification": "USER_PROVIDED_MEDIA",
                        "source": "META_WHATSAPP_CLOUD_API",
                        "artifact_sha256": hashlib.sha256(content).hexdigest(),
                        "size_bytes": len(content),
                        "mime_type": actual_mime,
                        "fetched_at_unix": int(time.time()),
                        **extraction,
                    },
                }
            )
        except MediaProcessingError as exc:
            payload.update(
                {
                    "extraction_status": "failed",
                    "extraction_error": exc.code,
                    "document_provenance": {
                        "classification": "USER_PROVIDED_MEDIA",
                        "source": "META_WHATSAPP_CLOUD_API",
                    },
                }
            )
        return replace(observation, payload=payload)


def media_summary(observation: Observation) -> dict[str, Any]:
    """Return content-free telemetry for one enriched media observation."""

    payload = dict(observation.payload)
    provenance = payload.get("document_provenance")
    provenance = provenance if isinstance(provenance, Mapping) else {}
    return {
        "status": payload.get("extraction_status"),
        "error_code": payload.get("extraction_error"),
        "mime_type": provenance.get("mime_type") or payload.get("mime_type"),
        "size_bytes": provenance.get("size_bytes"),
        "page_count": provenance.get("page_count"),
        "processed_pages": provenance.get("processed_pages"),
        "text_pages": provenance.get("text_pages"),
        "ocr_pages": provenance.get("ocr_pages"),
        "methods": provenance.get("methods") or [],
        "truncated": provenance.get("truncated"),
        "extracted_text_bytes": len(str(payload.get("extracted_text") or "").encode("utf-8")),
        "content_exported": False,
    }
