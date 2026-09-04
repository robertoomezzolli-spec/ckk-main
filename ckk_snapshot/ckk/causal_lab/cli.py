"""Command-line entry point for the sealed KAIROS causal experiment."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from ckk.observatory.store import ObservatoryStore

from .protocol import CAUSAL_PROTOCOL
from .report import build_report
from .runner import CausalExperiment


def main() -> None:
    parser = argparse.ArgumentParser(description="Run blinded causal-condition forks of KAIROS")
    parser.add_argument("--state-dir", type=Path, default=Path("/causal-observatory"))
    parser.add_argument("--output", type=Path, default=Path("/causal-observatory/causal-report.json"))
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    if not os.getenv("OPENAI_API_KEY") and not args.prepare_only:
        raise SystemExit("OPENAI_API_KEY is required for the real KAIROS model run")

    args.state_dir.mkdir(parents=True, exist_ok=True)
    store = ObservatoryStore(str(args.state_dir))
    try:
        if args.prepare_only:
            class NoCalls:
                def create(self, **_kwargs):
                    raise RuntimeError("prepare-only mode cannot invoke a model")

            experiment = CausalExperiment(store, NoCalls())
            source_hash, files = experiment.prepare()
            payload = {
                "status": "PREREGISTERED",
                "protocol_hash": CAUSAL_PROTOCOL.protocol_hash,
                "source_hash": source_hash,
                "source_files": files,
                "assignments": len(store.causal_assignments(CAUSAL_PROTOCOL.protocol_hash)),
            }
        else:
            from openai import OpenAI

            client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
            raw = CausalExperiment(store, client.responses).run().as_dict()
            payload = build_report(raw)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        print(json.dumps({
            "status": payload.get("status", "COMPLETED"),
            "protocol_hash": payload["protocol_hash"],
            "output": str(args.output),
            "secrets_printed": False,
        }, sort_keys=True))
    finally:
        store.close()


if __name__ == "__main__":
    main()
