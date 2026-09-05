#!/usr/bin/env python3
"""Depth-5 runner for the frozen causal-approach dilation observable."""
from pathlib import Path

import causal_approach_dilation_gate as gate

gate.LEVELS = 5
gate.OUT = Path(__file__).resolve().parents[1] / "results" / "causal_approach_dilation_gate_l5.json"
gate.main()
