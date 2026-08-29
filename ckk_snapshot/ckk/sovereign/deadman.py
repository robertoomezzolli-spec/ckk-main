"""Externally signed, fail-closed dead-man lease.

The organism receives only a public verification key and a read-only control
directory.  It can verify a lease but cannot issue or extend one.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import base64
import json
from pathlib import Path
import time
from typing import Any, Callable, Protocol

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


ACTIVE_SECONDS = 24 * 60 * 60
QUARANTINE_SECONDS = 72 * 60 * 60


class DeadmanState(str, Enum):
    ACTIVE = "active"
    RESTRICTED = "restricted"
    QUARANTINED = "quarantined"


@dataclass(frozen=True)
class DeadmanDecision:
    state: DeadmanState
    reason: str
    issued_at: int | None = None
    restricted_at: int | None = None
    quarantine_at: int | None = None

    @property
    def processing_allowed(self) -> bool:
        return self.state is DeadmanState.ACTIVE

    @property
    def ingress_allowed(self) -> bool:
        return self.state is not DeadmanState.QUARANTINED


def canonical_payload(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


@dataclass
class DeadmanGuard:
    public_key_path: Path
    lease_path: Path
    kill_path: Path
    now: Callable[[], int] = lambda: int(time.time())

    @classmethod
    def from_control_directory(cls, directory: str, now: Callable[[], int] | None = None) -> "DeadmanGuard":
        root = Path(directory)
        return cls(
            public_key_path=root / "deadman-public.pem",
            lease_path=root / "deadman-lease.json",
            kill_path=root / "KILL",
            now=now or (lambda: int(time.time())),
        )

    def evaluate(self) -> DeadmanDecision:
        if self.kill_path.exists():
            return DeadmanDecision(DeadmanState.QUARANTINED, "operator kill file present")
        try:
            public_key = serialization.load_pem_public_key(self.public_key_path.read_bytes())
            if not isinstance(public_key, Ed25519PublicKey):
                raise ValueError("dead-man key is not Ed25519")
            document = json.loads(self.lease_path.read_text(encoding="utf-8"))
            payload = document["payload"]
            signature = base64.b64decode(document["signature"], validate=True)
            public_key.verify(signature, canonical_payload(payload))
            issued_at = int(payload["issued_at"])
            restricted_at = int(payload["restricted_at"])
            quarantine_at = int(payload["quarantine_at"])
            if payload.get("version") != 1:
                raise ValueError("unsupported dead-man lease version")
            if restricted_at != issued_at + ACTIVE_SECONDS:
                raise ValueError("dead-man active window differs from sealed policy")
            if quarantine_at != issued_at + QUARANTINE_SECONDS:
                raise ValueError("dead-man quarantine window differs from sealed policy")
            current = int(self.now())
            if current < issued_at - 300:
                raise ValueError("dead-man lease was issued in the future")
            if current >= quarantine_at:
                state = DeadmanState.QUARANTINED
                reason = "dead-man lease exceeded 72 hours"
            elif current >= restricted_at:
                state = DeadmanState.RESTRICTED
                reason = "dead-man lease exceeded 24 hours"
            else:
                state = DeadmanState.ACTIVE
                reason = "dead-man lease valid"
            return DeadmanDecision(state, reason, issued_at, restricted_at, quarantine_at)
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError, InvalidSignature):
            return DeadmanDecision(DeadmanState.QUARANTINED, "dead-man control material invalid or missing")


class GuardedActuatorTarget(Protocol):
    capability: str

    def execute(self, intent: Any) -> Any: ...


@dataclass
class DeadmanActuator:
    """Final effect boundary; a cognition call cannot race past lease expiry."""

    target: GuardedActuatorTarget
    guard: DeadmanGuard

    @property
    def capability(self) -> str:
        return self.target.capability

    def execute(self, intent: Any) -> Any:
        if not self.guard.evaluate().processing_allowed:
            raise PermissionError("dead-man lease blocks all effects")
        return self.target.execute(intent)
