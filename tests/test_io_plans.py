from copy import deepcopy

import pytest

from fpv_tune.io import InputError, config_from_headers, list_logs, parse_config, read_csv, select_log
from fpv_tune.planning import compile_plan, normalize_known, review_table


def proposal(key="p_pitch", value=42):
    return {"changes": [{"key": key, "value": value, "reason": "Synthetic format and traceability test only.",
                         "evidence": ["axes.pitch.tracking.normalized_mae"]}]}


def test_header_after_binary_without_newline_is_found(tmp_path):
    path = tmp_path / "flight.bbl"
    signature = b"H Product:Blackbox flight data recorder by Nicholas Sherlock\nH Firmware revision:Betaflight 4.5.2\n"
    path.write_bytes(signature + b"\x00binary" + signature + b"\x01tail")
    logs = list_logs(path)
    assert len(logs) == 2
    assert logs[1]["headers"]["Firmware revision"] == "Betaflight 4.5.2"
    with pytest.raises(InputError, match="does not exist"):
        select_log(logs, 9)


def test_multi_profile_dump_requires_scope(tmp_path):
    path = tmp_path / "dump.txt"
    path.write_text("# Betaflight / STM32H743 4.5.2\nset gyro_lpf2_static_hz = 500\nprofile 0\nset p_pitch = 39\nprofile 1\nset p_pitch = 88\nprofile 0\n", encoding="utf-8")
    with pytest.raises(InputError, match="multiple"):
        parse_config(path)
    snapshot = parse_config(path, 0)
    assert snapshot["values"]["p_pitch"] == 39
    assert snapshot["values"]["gyro_lpf2_static_hz"] == 500
    assert snapshot["firmware"] == "4.5.2"


def test_enum_one_is_setpoint_not_gyro():
    known, invalid = normalize_known({"iterm_relax_type": 1, "gyro_lpf1_type": 0})
    assert not invalid
    assert known == {"iterm_relax_type": "SETPOINT", "gyro_lpf1_type": "PT1"}


def test_unknown_version_does_not_apply_452_enum_meanings():
    rows = review_table({"firmware": "2026.6.2", "values": {"gyro_lpf1_type": 1}})
    row = next(item for item in rows if item["key"] == "gyro_lpf1_type")
    assert row["current"] == 1
    assert row["status"] == "unverified_version"


def test_csv_units_whitespace_and_ambiguity(tmp_path):
    path = tmp_path / "input.csv"
    path.write_text("time (us), gyroADC[0] (deg/s)\n0, 1\n500, 2\n", encoding="utf-8")
    frame, units = read_csv(path)
    assert list(frame.columns) == ["time", "gyroADC[0]"]
    assert units["gyroADC[0]"] == "deg/s"


def test_partial_headers_do_not_invent_yaw_d():
    snapshot = config_from_headers({"pitchPID": "39,71,44"})
    assert "d_yaw" not in snapshot["values"]
    assert snapshot["values"]["d_pitch"] == 44


def test_manual_pid_plan_disables_simplified_and_has_rollback(measured):
    result = compile_plan(measured, measured["config"], proposal(), 0)
    assert "set p_pitch = 42" in result["candidate_cli"]
    assert "set simplified_pids_mode = OFF" in result["candidate_cli"]
    assert "set p_pitch = 40" in result["rollback_cli"]
    assert "set simplified_pids_mode = RPY" in result["rollback_cli"]
    assert "set iterm_relax_type = SETPOINT" in result["full_cli"]
    assert not result["candidate_cli"].splitlines()[-1] == "save"
    assert result["status"] == "candidate_not_flight_validated"


def test_pid_and_filter_changes_allowed_together(measured):
    changes = proposal()
    changes["changes"].append({"key": "gyro_lpf1_dyn_min_hz", "value": 240,
                               "reason": "Synthetic combined plan test.",
                               "evidence": ["axes.roll.gyro_post.band_rms.180_450"]})
    result = compile_plan(measured, measured["config"], changes, 0)
    assert "set p_pitch = 42" in result["candidate_cli"]
    assert "set gyro_lpf1_dyn_min_hz = 240" in result["candidate_cli"]
    assert "set simplified_gyro_filter = OFF" in result["candidate_cli"]


@pytest.mark.parametrize("key,value", [("unknown_parameter", 10), ("p_pitch", 999), ("p_pitch", "42\nsave"), ("p_pitch", True)])
def test_unknown_out_of_bounds_and_command_injection_rejected(measured, key, value):
    with pytest.raises(InputError):
        compile_plan(measured, measured["config"], proposal(key, value), 0)


def test_missing_evidence_and_missing_value_rejected(measured):
    changes = proposal()
    changes["changes"][0]["evidence"] = ["axes.pitch.not_measured"]
    with pytest.raises(InputError, match="evidence"):
        compile_plan(measured, measured["config"], changes, 0)
    with pytest.raises(InputError, match="Current value"):
        compile_plan(measured, measured["config"], proposal("p_yaw", 40), 0)


def test_old_log_new_config_mismatch_rejected(measured):
    config = deepcopy(measured["config"])
    config["values"]["p_pitch"] = 44
    with pytest.raises(InputError, match="does not match"):
        compile_plan(measured, config, proposal(), 0)


def test_unknown_firmware_does_not_generate_cli(measured):
    current = deepcopy(measured)
    current["config"]["firmware"] = "2025.12.0"
    with pytest.raises(InputError, match="4.5.2"):
        compile_plan(current, current["config"], proposal(), 0)


def test_d_min_cannot_exceed_d_max(measured):
    with pytest.raises(InputError, match="D-min exceeds"):
        compile_plan(measured, measured["config"], proposal("d_min_pitch", 50), 0)


def test_quality_blockers_block_cli(measured):
    current = deepcopy(measured)
    current["quality"]["planning_blockers"] = ["missing_units"]
    with pytest.raises(InputError, match="quality"):
        compile_plan(current, current["config"], proposal(), 0)


def test_save_only_when_explicit(measured):
    result = compile_plan(measured, measured["config"], proposal(), 0, include_save=True)
    assert result["candidate_cli"].splitlines()[-1] == "save"
    assert result["rollback_cli"].splitlines()[-1] == "save"
