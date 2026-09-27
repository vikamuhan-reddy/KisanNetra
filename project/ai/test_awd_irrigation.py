"""AWD irrigation rules — the flooded-paddy case that soil moisture cannot serve.

The point under test: under standing water the soil probes read saturated, so a
moisture-threshold rule never fires and the field is never irrigated on time.
Water depth in the AWD tube is what carries the signal. These tests fail if that
inversion is ever undone.

Run: pytest ai/test_awd_irrigation.py
"""
import pytest

from step6_rule_engine import (
    AWD_REFLOOD_DEPTH_CM,
    AWD_TUBE_FLOOR_CM,
    evaluate_irrigation,
)


def reading(**over):
    """A sane flooded-paddy reading; override one field per test."""
    s = {
        "timestamp": "2026-09-23T00:00:00Z",
        "rain": False,
        "tank_level": 80.0,
        "flow_lpm": 2.0,
        # Saturated, as flooded paddy always is. No moisture rule may fire here.
        "surface_moisture": 95.0,
        "root_moisture": 92.0,
        "water_depth_cm": 3.0,
        "sensor_status": {
            "tank_level": "VALID",
            "surface_moisture": "VALID",
            "root_moisture": "VALID",
            "water_depth_cm": "VALID",
        },
    }
    s.update(over)
    return s


def test_standing_water_does_not_irrigate():
    r = evaluate_irrigation(reading(water_depth_cm=3.0))
    assert r["action"] == "NO_ACTION"
    assert "above surface" in " ".join(r["reason"])


def test_drawdown_above_threshold_is_not_a_fault():
    """Water below the surface but above the re-flood depth is AWD working."""
    r = evaluate_irrigation(reading(water_depth_cm=AWD_REFLOOD_DEPTH_CM + 5))
    assert r["action"] == "NO_ACTION"
    assert "as intended" in " ".join(r["reason"])


def test_reflood_threshold_triggers_irrigation():
    r = evaluate_irrigation(reading(water_depth_cm=AWD_REFLOOD_DEPTH_CM - 1))
    assert r["action"] == "IRRIGATE"
    assert "re-flood" in " ".join(r["reason"]).lower()


def test_saturated_probes_never_block_a_needed_reflood():
    """The regression this whole change exists to prevent.

    Probes pegged at saturation, water well below the re-flood depth. A
    moisture-threshold rule would sit at NO_ACTION forever.
    """
    r = evaluate_irrigation(
        reading(water_depth_cm=-20.0, surface_moisture=99.0, root_moisture=99.0)
    )
    assert r["action"] == "IRRIGATE"


def test_drained_field_falls_back_to_soil_moisture():
    """Below the tube floor the field is genuinely drained; probes govern."""
    r = evaluate_irrigation(
        reading(water_depth_cm=AWD_TUBE_FLOOR_CM - 1, surface_moisture=10.0, root_moisture=8.0)
    )
    assert r["action"] == "IRRIGATE"
    assert "drained" in " ".join(r["reason"])


def test_failed_tube_degrades_confidence_and_says_so():
    """A failed sensor is reported, never silently replaced with a number."""
    s = reading()
    s["sensor_status"]["water_depth_cm"] = "FAILED"
    r = evaluate_irrigation(s)
    assert r["confidence"] == "LOW"
    assert "MANUAL CHECK" in " ".join(r["reason"])


def test_rain_still_short_circuits_everything():
    r = evaluate_irrigation(reading(rain=True, water_depth_cm=-20.0))
    assert r["action"] == "HOLD"


def test_low_tank_blocks_even_when_reflood_is_due():
    r = evaluate_irrigation(reading(water_depth_cm=-20.0, tank_level=5.0))
    assert r["action"] == "HOLD"
    assert r["blocked"] is True


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
