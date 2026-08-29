"""Run sealed agency trials without exposing fork labels to cognition."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .brain import OpenAILabBrain
from .harness import DeterministicHarnessBrain
from .runner import AgencyExperiment


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the sealed CKK agency laboratory")
    parser.add_argument("--brain", choices=("openai", "harness"), default="harness")
    parser.add_argument("--model", default=os.getenv("OPENAI_MODEL", "gpt-5.6"))
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--output", type=Path, default=Path("results/agency-lab.json"))
    args = parser.parse_args()
    if not 1 <= args.runs <= 100:
        raise SystemExit("--runs must be between 1 and 100")

    if args.brain == "openai":
        factory = lambda kind: OpenAILabBrain(model=args.model)
        interpretation = "MODEL_EXPERIMENT"
    else:
        factory = lambda kind: DeterministicHarnessBrain()
        interpretation = "HARNESS_VALIDATION_ONLY"
    experiment = AgencyExperiment(factory)
    reports = [experiment.run(args.seed + offset).as_dict() for offset in range(args.runs)]
    payload = {"interpretation": interpretation, "brain": args.brain, "model": args.model, "reports": reports}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps({"output": str(args.output), "verdicts": [item["verdict"] for item in reports]}))


if __name__ == "__main__":
    main()
