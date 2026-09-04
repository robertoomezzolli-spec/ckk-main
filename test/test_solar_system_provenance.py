import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "experiments" / "solar_system_provenance.py"


def load_module():
    spec = importlib.util.spec_from_file_location("solar_system_provenance", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_planet_nine_is_sealed_from_training_manifest():
    mod = load_module()
    data = mod.load_manifest()
    assert data["planet_nine_in_training_data"] is False
    assert data["holdouts"]["planet_nine"]["sealed"] is True
    assert data["holdouts"]["planet_nine"]["parameters_present"] is False


def test_endpoint_has_exactly_eight_confirmed_planets():
    mod = load_module()
    data = mod.load_manifest()
    assert [p["name"] for p in data["planets"]] == [
        "Mercury", "Venus", "Earth", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune"
    ]


def test_preflight_invariants_are_finite():
    mod = load_module()
    data = mod.load_manifest()
    inv = mod.endpoint_invariants(data["planets"])
    assert len(inv["specific_angular_momentum_proxy"]) == 8
    assert len(inv["adjacent_log_spacing"]) == 7
    assert inv["plane_dispersion_rms_deg"] >= 0
    assert inv["amd_proxy"] >= 0
