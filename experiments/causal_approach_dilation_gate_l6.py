#!/usr/bin/env python3
"""Depth-6 runner so level-5 boundary-adjacent states get one complete outgoing sweep."""
from pathlib import Path

import causal_approach_dilation_gate as gate

gate.LEVELS = 6
gate.OUT = Path(__file__).resolve().parents[1] / "results" / "causal_approach_dilation_gate_l6.json"
gate.main()
