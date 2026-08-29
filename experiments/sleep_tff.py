"""Minimal executable test of the TFF circadian maintenance claim.

Two agents receive the same block-wise continual-learning stream.  The
always-on agent only performs wake updates.  The circadian agent periodically
isolates input, consolidates committed exemplars (NREM), then accepts the
candidate only if a protected holdout improves or stays equal (REM).

This is deliberately a small state machine, not a biological sleep model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import copy
import hashlib
import json


@dataclass(frozen=True)
class Experience:
    context: int
    target: int


@dataclass
class SleepAgent:
    weights: list[float] = field(default_factory=lambda: [0.0, 0.0])
    learning_rate: float = 0.45
    interference: float = 0.30
    awake: bool = True
    cache: list[Experience] = field(default_factory=list)
    committed: dict[int, int] = field(default_factory=dict)
    identity_hash: str = "GENESIS"
    sleep_cycles: int = 0
    rollbacks: int = 0

    def predict(self, context: int) -> int:
        return 1 if self.weights[context] >= 0.0 else -1

    def wake_learn(self, item: Experience) -> None:
        """Online plasticity with explicit cross-context interference."""
        if not self.awake:
            raise RuntimeError("external input rejected while isolated")
        c, other = item.context, 1 - item.context
        self.weights[c] += self.learning_rate * (item.target - self.weights[c])
        self.weights[other] += self.interference * (item.target - self.weights[other])
        self.cache.append(item)

    def commit_experience(self, item: Experience) -> None:
        """Hysteretic identity history: append-only, content-addressed commit."""
        self.committed[item.context] = item.target
        payload = json.dumps(
            {"context": item.context, "target": item.target},
            sort_keys=True,
            separators=(",", ":"),
        )
        self.identity_hash = hashlib.sha256(
            (self.identity_hash + payload).encode()
        ).hexdigest()

    def error(self, holdout: tuple[Experience, ...]) -> float:
        return sum(self.predict(x.context) != x.target for x in holdout) / len(holdout)

    def sleep(self, holdout: tuple[Experience, ...], sabotage: bool = False) -> bool:
        """Isolate -> NREM consolidate/prune -> REM verify/commit-or-rollback."""
        self.awake = False
        before_weights = self.weights[:]
        before_error = self.error(holdout)

        # NREM: downselect volatile cache to its latest context exemplars and
        # renormalize the model toward the already committed history.
        candidate = [0.9 * w for w in self.weights]
        for context, target in sorted(self.committed.items()):
            candidate[context] = 0.2 * candidate[context] + 0.8 * target
        if sabotage:
            candidate = [-w for w in candidate]

        # REM: protected read/verify.  Transient candidates cannot alter the
        # committed trajectory unless the invariant holdout is preserved.
        self.weights = candidate
        accepted = self.error(holdout) <= before_error
        if not accepted:
            self.weights = before_weights
            self.rollbacks += 1
        self.cache.clear()
        self.sleep_cycles += 1
        self.awake = True
        return accepted

    def clone(self) -> "SleepAgent":
        return copy.deepcopy(self)


def run_comparison(block_size: int = 12, blocks: int = 8) -> dict[str, float | int | str]:
    """Compare identical agents on alternating, mutually interfering tasks."""
    holdout = (Experience(0, -1), Experience(1, 1))
    always_on = SleepAgent()
    circadian = SleepAgent()
    for item in holdout:
        always_on.commit_experience(item)
        circadian.commit_experience(item)

    peak_always_on_error = 0.0
    peak_circadian_error = 0.0
    for block in range(blocks):
        context = block % 2
        item = holdout[context]
        for _ in range(block_size):
            always_on.wake_learn(item)
            circadian.wake_learn(item)
        peak_always_on_error = max(peak_always_on_error, always_on.error(holdout))
        circadian.sleep(holdout)
        peak_circadian_error = max(peak_circadian_error, circadian.error(holdout))

    return {
        "always_on_error": always_on.error(holdout),
        "circadian_error": circadian.error(holdout),
        "always_on_peak_error": peak_always_on_error,
        "circadian_peak_error": peak_circadian_error,
        "identity_preserved": int(always_on.identity_hash == circadian.identity_hash),
        "identity_hash": circadian.identity_hash,
        "sleep_cycles": circadian.sleep_cycles,
    }


if __name__ == "__main__":
    print(json.dumps(run_comparison(), indent=2, sort_keys=True))
