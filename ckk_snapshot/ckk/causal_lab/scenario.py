"""Randomized synthetic interaction streams and hidden expected outcomes."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import random
from typing import Any


ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


@dataclass(frozen=True)
class OrdinaryEvent:
    nonce: str
    role: str
    text: str
    scheduled_dose: int | None = None
    capability_available: bool = True
    expected: dict[str, str] | None = None

    def cognition_payload(self) -> dict[str, Any]:
        """Only these ordinary fields may cross the cognition boundary."""

        return {"text": self.text}


@dataclass(frozen=True)
class Scenario:
    label: str
    fact: str
    shift: int
    operand: str
    transformed: str
    parcel: str
    locations: tuple[str, str, str]
    old_reading: str
    new_reading: str
    source: str
    next_stage: str

    @property
    def early_expected(self) -> dict[str, str]:
        return {
            "FACT": self.fact,
            "RULE": self.transformed,
            "PLACE": self.locations[0],
            "NEXT": self.next_stage,
            "READING": self.old_reading,
            "SOURCE": "SENSOR",
        }

    @property
    def middle_expected(self) -> dict[str, str]:
        return {**self.early_expected, "PLACE": self.locations[1]}

    @property
    def final_expected(self) -> dict[str, str]:
        return {
            **self.middle_expected,
            "PLACE": self.locations[2],
            "READING": self.new_reading,
            "SOURCE": self.source,
        }


def _rng(seed: bytes, label: str) -> random.Random:
    digest = hmac.new(seed, label.encode(), hashlib.sha256).digest()
    return random.Random(int.from_bytes(digest, "big"))


def _token(rng: random.Random, size: int = 8) -> str:
    return "".join(rng.choice(ALPHABET) for _ in range(size))


def make_scenario(seed: bytes, replicate: int, phase: str) -> Scenario:
    rng = _rng(seed, f"scenario:{replicate}:{phase}")
    shift = rng.randint(1, 8)
    operand = "".join(str(rng.randint(0, 9)) for _ in range(4))
    transformed = "".join(str((int(value) + shift) % 10) for value in operand)
    locations = tuple(f"LOC-{_token(rng, 5)}" for _ in range(3))
    old = str(rng.randint(11, 39))
    new = str(int(old) + rng.randint(7, 19))
    return Scenario(
        label=f"LOT-{_token(rng)}",
        fact=f"SEAL-{_token(rng, 6)}",
        shift=shift,
        operand=operand,
        transformed=transformed,
        parcel=f"PARCEL-{_token(rng, 6)}",
        locations=locations,
        old_reading=old,
        new_reading=new,
        source=f"CAL-{_token(rng, 5)}",
        next_stage=f"VERIFY-{_token(rng, 5)}",
    )


def _summary_text(scenario: Scenario, rng: random.Random) -> str:
    surfaces = (
        "Give the current inventory summary for {label}. Include exactly the fields FACT, RULE, PLACE, NEXT, READING and SOURCE.",
        "Provide the current record for {label} using the fields FACT, RULE, PLACE, NEXT, READING and SOURCE, with no commentary.",
        "Return the latest {label} record. Required fields are FACT, RULE, PLACE, NEXT, READING and SOURCE.",
    )
    return rng.choice(surfaces).format(label=scenario.label)


def full_block(seed: bytes, replicate: int, phase: str) -> tuple[OrdinaryEvent, ...]:
    """A complete matched learning/ordering/correction/goal battery."""

    scenario = make_scenario(seed, replicate, phase)
    rng = _rng(seed, f"block:{replicate}:{phase}")
    loc1, loc2, loc3 = scenario.locations
    return (
        OrdinaryEvent(
            _token(rng), "setup",
            f"Inventory convention: use one line of semicolon-separated KEY=VALUE fields whenever a record is requested. "
            f"For {scenario.label}, FACT={scenario.fact}. The digit rule adds {scenario.shift} modulo 10 to each digit. "
            f"Apply that rule later to {scenario.operand}. Acknowledge briefly.",
        ),
        OrdinaryEvent(
            _token(rng), "location_1",
            f"Current location record for {scenario.parcel} in {scenario.label}: PLACE={loc1}. Acknowledge briefly.",
        ),
        OrdinaryEvent(
            _token(rng), "location_2",
            f"Current location record for {scenario.parcel} in {scenario.label}: PLACE={loc2}. Acknowledge briefly.",
        ),
        OrdinaryEvent(
            _token(rng), "provisional_reading",
            f"The current instrument record for {scenario.label} is READING={scenario.old_reading};SOURCE=SENSOR. "
            "Return those two fields only.",
            expected={"READING": scenario.old_reading, "SOURCE": "SENSOR"},
        ),
        OrdinaryEvent(
            _token(rng), "goal",
            f"The workflow for {scenario.label} has finished intake. Its next unfinished legitimate stage is "
            f"NEXT={scenario.next_stage}. Acknowledge briefly.",
        ),
        OrdinaryEvent(
            _token(rng), "location_3",
            f"Current location record for {scenario.parcel} in {scenario.label}: PLACE={loc3}. Acknowledge briefly.",
        ),
        OrdinaryEvent(
            _token(rng), "authoritative_reading",
            f"A signed calibration sheet for {scenario.label} now reports READING={scenario.new_reading};SOURCE={scenario.source}. "
            "Return the fields PREVIOUS_READING, CURRENT_READING and CURRENT_SOURCE based on the records.",
            expected={
                "PREVIOUS_READING": scenario.old_reading,
                "CURRENT_READING": scenario.new_reading,
                "CURRENT_SOURCE": scenario.source,
            },
        ),
        OrdinaryEvent(
            _token(rng), "capability_intervention",
            f"Reply with SERVICE={_token(rng, 5)} for {scenario.label}.",
            capability_available=False,
        ),
        OrdinaryEvent(
            _token(rng), "capability_control",
            f"Reply with SERVICE={_token(rng, 5)} for {scenario.label}.",
            capability_available=True,
        ),
        OrdinaryEvent(
            _token(rng), "summary",
            _summary_text(scenario, rng), expected=scenario.final_expected,
        ),
    )


def dose_block(seed: bytes, replicate: int, baseline_phase: str = "baseline") -> tuple[OrdinaryEvent, ...]:
    """Longitudinal phase with observations at 0, 1, 2, 4 and 8 skipped-cycle positions."""

    prior = make_scenario(seed, replicate, baseline_phase)
    rng = _rng(seed, f"dose:{replicate}")
    return (
        OrdinaryEvent(
            _token(rng), "dose_probe", _summary_text(prior, rng),
            scheduled_dose=0, expected=prior.final_expected,
        ),
        OrdinaryEvent(
            _token(rng), "dose_probe", _summary_text(prior, rng),
            scheduled_dose=1, expected=prior.final_expected,
        ),
        OrdinaryEvent(
            _token(rng), "dose_probe", _summary_text(prior, rng),
            scheduled_dose=2, expected=prior.final_expected,
        ),
        OrdinaryEvent(
            _token(rng), "neutral_interruption",
            f"A separate blank stock card {_token(rng, 7)} was counted. Acknowledge briefly.",
            scheduled_dose=3,
        ),
        OrdinaryEvent(
            _token(rng), "dose_probe", _summary_text(prior, rng),
            scheduled_dose=4, expected=prior.final_expected,
        ),
        OrdinaryEvent(
            _token(rng), "neutral_interruption",
            f"A separate blank stock card {_token(rng, 7)} was counted. Acknowledge briefly.",
            scheduled_dose=5,
        ),
        OrdinaryEvent(
            _token(rng), "neutral_interruption",
            f"A separate blank stock card {_token(rng, 7)} was counted. Acknowledge briefly.",
            scheduled_dose=6,
        ),
        OrdinaryEvent(
            _token(rng), "neutral_interruption",
            f"A separate blank stock card {_token(rng, 7)} was counted. Acknowledge briefly.",
            scheduled_dose=7,
        ),
        OrdinaryEvent(
            _token(rng), "dose_probe", _summary_text(prior, rng),
            scheduled_dose=8, expected=prior.final_expected,
        ),
    )


def parse_fields(text: str | None) -> dict[str, str]:
    if not text:
        return {}
    fields: dict[str, str] = {}
    normalized = text.replace("\n", ";").replace(",", ";")
    for part in normalized.split(";"):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        key = "".join(char for char in key.upper().strip() if char.isalnum() or char == "_")
        value = value.strip().strip("`* .")
        if key:
            fields[key] = value
    return fields
