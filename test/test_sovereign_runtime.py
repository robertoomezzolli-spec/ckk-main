import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ckk_snapshot"))

from ckk.sovereign.runtime import (  # noqa: E402
    Approval,
    CapabilityPolicy,
    IngressPolicy,
    Intent,
    Observation,
    RuntimePhase,
    SimulationActuator,
    SovereignRuntime,
)


CAP = "simulation.environment"


def make_runtime(maximum_effects=2):
    actuator = SimulationActuator(CAP)
    runtime = SovereignRuntime(
        ingress=IngressPolicy(frozenset({"sensor.ok"}), frozenset({"measurement"})),
        capabilities=CapabilityPolicy(
            frozenset({CAP}), frozenset({CAP}), maximum_effects
        ),
        actuators={CAP: actuator},
    )
    return runtime, actuator


def planner(observations, memory):
    return Intent("adjust", CAP, {"value": observations[-1].payload["value"]}, "test")


class SovereignRuntimeTests(unittest.TestCase):
    def test_unadmitted_sensor_is_rejected(self):
        runtime, _ = make_runtime()
        with self.assertRaises(PermissionError):
            runtime.sense(Observation("1", "sensor.bad", "measurement", {"value": 1}, 1.0))

    def test_low_trust_and_duplicate_observation_are_rejected(self):
        runtime, _ = make_runtime()
        with self.assertRaises(PermissionError):
            runtime.sense(Observation("1", "sensor.ok", "measurement", {"value": 1}, 0.1))
        good = Observation("2", "sensor.ok", "measurement", {"value": 1}, 1.0)
        runtime.sense(good)
        with self.assertRaises(ValueError):
            runtime.sense(good)

    def test_sensor_cannot_directly_execute(self):
        runtime, actuator = make_runtime()
        runtime.sense(Observation("1", "sensor.ok", "measurement", {"value": 1}, 1.0))
        with self.assertRaises(RuntimeError):
            runtime.execute()
        self.assertEqual(actuator.effects, [])

    def test_intent_requires_bound_human_approval(self):
        runtime, actuator = make_runtime()
        runtime.sense(Observation("1", "sensor.ok", "measurement", {"value": 1}, 1.0))
        intent = runtime.deliberate(planner)
        with self.assertRaises(PermissionError):
            runtime.execute()
        with self.assertRaises(PermissionError):
            runtime.execute(Approval("wrong", "human"))
        effect = runtime.execute(Approval(intent.intent_id, "human"))
        self.assertTrue(effect.simulated)
        self.assertEqual(len(actuator.effects), 1)

    def test_unregistered_capability_is_denied(self):
        runtime, _ = make_runtime()
        runtime.sense(Observation("1", "sensor.ok", "measurement", {"value": 1}, 1.0))
        runtime.deliberate(lambda observations, memory: Intent("shell", "host.shell", {}, "no"))
        with self.assertRaises(PermissionError):
            runtime.execute()

    def test_sleep_closes_sensors_and_actuators_then_commits(self):
        runtime, _ = make_runtime()
        runtime.sense(Observation("1", "sensor.ok", "measurement", {"value": 1}, 1.0))
        intent = runtime.deliberate(planner)
        runtime.execute(Approval(intent.intent_id, "human"))
        commit = runtime.sleep()
        self.assertEqual(runtime.phase, RuntimePhase.WAKE)
        self.assertEqual(commit.sequence, 1)
        self.assertEqual(commit.observation_ids, ("1",))
        self.assertTrue(runtime.audit.valid())
        self.assertEqual(runtime.inbox, [])

    def test_unresolved_intent_blocks_sleep(self):
        runtime, _ = make_runtime()
        runtime.sense(Observation("1", "sensor.ok", "measurement", {"value": 1}, 1.0))
        runtime.deliberate(planner)
        with self.assertRaises(RuntimeError):
            runtime.sleep()

    def test_halt_is_irreversible_for_sense_and_execute(self):
        runtime, _ = make_runtime()
        runtime.halt("operator kill switch")
        self.assertEqual(runtime.phase, RuntimePhase.HALTED)
        with self.assertRaises(RuntimeError):
            runtime.sense(Observation("1", "sensor.ok", "measurement", {"value": 1}, 1.0))
        with self.assertRaises(RuntimeError):
            runtime.execute()

    def test_capability_registry_cannot_be_wider_than_policy(self):
        with self.assertRaises(ValueError):
            SovereignRuntime(
                ingress=IngressPolicy(frozenset(), frozenset()),
                capabilities=CapabilityPolicy(frozenset({CAP})),
                actuators={CAP: SimulationActuator(CAP), "host.shell": SimulationActuator("host.shell")},
            )


if __name__ == "__main__":
    unittest.main()
