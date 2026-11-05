"""Reproductions discovered during independent realistic skill evaluation."""

from copy import deepcopy

import numpy as np
import pytest

from fpv_tune.analysis import analyze, compare
from fpv_tune.io import InputError
from fpv_tune.planning import compile_plan, registry


def change(key, value):
    return {"key": key, "value": value, "reason": "Software regression, not a flight recommendation.",
            "evidence": ["axes.pitch.dterm.band_rms.180_450"]}


def test_off_literal_does_not_enable_high_resolution(flight):
    frame, units, snapshot = flight
    snapshot = deepcopy(snapshot)
    snapshot["values"]["blackbox_high_resolution"] = "OFF"
    report, _ = analyze(frame, units, snapshot, {"sha256": "a", "name": "test"})
    assert "high_resolution_signal_scaling_not_validated" not in report["quality"]["planning_blockers"]
    compile_plan(report, snapshot, {"changes": [change("p_pitch", 42)]}, 0)


@pytest.mark.parametrize("key,bad", [
    ("tpa_breakpoint", 900), ("tpa_low_breakpoint", 950), ("dyn_notch_min_hz", 600),
    ("dyn_notch_q", 0), ("rpm_filter_q", 0), ("rpm_filter_min_hz", 0), ("rpm_filter_lpf_hz", 0),
    ("anti_gravity_cutoff_hz", 0), ("iterm_relax_cutoff", 0), ("throttle_boost_cutoff", 0),
    ("f_pitch", 1001), ("simplified_gyro_filter_multiplier", 0),
])
def test_firmware_invalid_parameters_rejected(key, bad):
    with pytest.raises(InputError):
        registry()[key].normalize(bad)


def test_cannot_enable_simplified_with_manual_pid_when_currently_off(measured):
    report = deepcopy(measured)
    report["config"]["values"]["simplified_pids_mode"] = "OFF"
    with pytest.raises(InputError, match="conflict"):
        compile_plan(report, report["config"], {"changes": [change("p_pitch", 42), change("simplified_pids_mode", "RPY")]}, 0)


def test_manual_lpf_with_its_multiplier_rejected(measured):
    report = deepcopy(measured)
    report["config"]["values"]["simplified_gyro_filter_multiplier"] = 100
    with pytest.raises(InputError, match="multipliers"):
        compile_plan(report, report["config"], {"changes": [change("gyro_lpf1_dyn_min_hz", 240), change("simplified_gyro_filter_multiplier", 110)]}, 0)


def test_radian_setpoints_convert_to_the_same_physical_tracking(flight):
    frame, units, snapshot = flight
    original, _ = analyze(frame, units, snapshot, {"sha256": "a", "name": "degrees"})
    radians, rad_units = frame.copy(), dict(units)
    for idx in range(3):
        radians[f"setpoint[{idx}]"] *= np.pi / 180
        rad_units[f"setpoint[{idx}]"] = "rad/s"
    converted, _ = analyze(radians, rad_units, snapshot, {"sha256": "b", "name": "radians"})
    assert converted["quality"]["setpoint_units_confirmed"]
    assert converted["axes"]["pitch"]["tracking"]["normalized_mae"] == pytest.approx(original["axes"]["pitch"]["tracking"]["normalized_mae"])
    assert [w["setpoint_bin"] for w in converted["windows"]] == [w["setpoint_bin"] for w in original["windows"]]
    assert compare(original, converted)["common_strata"]


def test_unknown_setpoint_scale_blocks_plan(flight):
    frame, units, snapshot = flight
    units = {**units, "setpoint[0]": "unknown"}
    report, _ = analyze(frame, units, snapshot, {"sha256": "a", "name": "unknown"})
    assert "setpoint_units_or_fields_unconfirmed" in report["quality"]["planning_blockers"]


@pytest.mark.parametrize("key,old,new", [("d_max_gain", 37, 40), ("d_max_advance", 20, 22)])
def test_dynamic_d_controls_do_not_require_a_gain_or_advance_axis(measured, key, old, new):
    report = deepcopy(measured)
    report["config"]["values"][key] = old
    report["config"]["values"]["d_roll"] = 36
    plan = compile_plan(report, report["config"], {"changes": [change(key, new)]}, 0)
    assert f"set {key} = {new}" in plan["candidate_cli"]


def test_analysis_profile_must_match_executable_profile(measured):
    config = deepcopy(measured["config"])
    config["profile"] = 1
    with pytest.raises(InputError, match="analyzed flight profile"):
        compile_plan(measured, config, {"changes": [change("p_pitch", 42)]}, 1)


def test_rpm_array_is_bounded_and_not_command_text():
    assert registry()["rpm_filter_weights"].normalize("100, 80, 0") == "100,80,0"
    for value in ("100,100,100\nsave", "100,100", [True, 100, 100], "101,100,100"):
        with pytest.raises(InputError):
            registry()["rpm_filter_weights"].normalize(value)
