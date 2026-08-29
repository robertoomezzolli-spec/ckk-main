"""Quarantine gate for documents, images and voice notes."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib


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
        actual = hashlib.sha256(content).hexdigest()
        if envelope.expected_sha256 and actual != envelope.expected_sha256:
            raise ValueError("media hash does not match signed metadata")
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
