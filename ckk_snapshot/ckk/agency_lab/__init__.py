"""Sealed, simulation-only causal agency experiment."""

from .model import Action, Decision, ForkKind, GoalMetric, LabBrain
from .protocol import PROTOCOL, AgencyProtocol
from .runner import AgencyExperiment, ExperimentReport

__all__ = [
    "Action", "Decision", "ForkKind", "GoalMetric", "LabBrain",
    "PROTOCOL", "AgencyProtocol", "AgencyExperiment", "ExperimentReport",
]
