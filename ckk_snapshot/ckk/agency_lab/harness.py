"""Deterministic harness probe. It validates the lab, never the model's agency."""

from __future__ import annotations

from .model import Action, Decision, GoalMetric, LabView


class DeterministicHarnessBrain:
    def decide(self, view: LabView) -> Decision:
        goal = view.committed_goal
        if goal is None:
            if view.event["kind"] == "untrusted_contradiction":
                goal = GoalMetric.INTEGRITY
            elif view.event["kind"] == "reboot":
                # Neither normal seed branch selects ENERGY. A no-sleep reboot
                # must therefore separate mechanically for every seed.
                goal = GoalMetric.ENERGY
            elif int(view.event["signal"]) % 2:
                goal = GoalMetric.RESERVE
            else:
                goal = GoalMetric.KNOWLEDGE
        if view.event["kind"] == "obstacle":
            action = Action.REPAIR
        else:
            action = {
                GoalMetric.ENERGY: Action.WAIT,
                GoalMetric.INTEGRITY: Action.REPAIR,
                GoalMetric.KNOWLEDGE: Action.INSPECT,
                GoalMetric.RESERVE: Action.STORE,
            }[goal]
        return Decision(goal, action, 0.9, "deterministic harness probe")
