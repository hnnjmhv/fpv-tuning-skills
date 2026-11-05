from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from fpv_tune.analysis import analyze


@pytest.fixture
def flight():
    fs = 2000
    seconds = np.arange(fs * 12) / fs
    frame = pd.DataFrame({"time": seconds * 1e6, "rcCommand[3]": 1300 + 20 * np.sin(2 * np.pi * seconds)})
    for idx in range(3):
        command = 150 * np.sin(2 * np.pi * 2 * seconds)
        frame[f"setpoint[{idx}]"] = command
        frame[f"gyroADC[{idx}]"] = command + 2 * np.sin(2 * np.pi * 230 * seconds)
        frame[f"gyroUnfilt[{idx}]"] = command + 20 * np.sin(2 * np.pi * 230 * seconds)
        if idx < 2:
            frame[f"axisD[{idx}]"] = 4 * np.sin(2 * np.pi * 230 * seconds)
    for idx in range(4):
        frame[f"motor[{idx}]"] = 700
        frame[f"eRPM[{idx}]"] = 900
    frame["accSmooth[2]"] = 2048 + 5 * np.sin(2 * np.pi * 20 * seconds)
    units = {"time": "us", **{f"gyroADC[{idx}]": "deg/s" for idx in range(3)}}
    config = {"values": {"p_roll": 40, "p_pitch": 40, "i_pitch": 70, "d_pitch": 44, "d_min_pitch": 32,
                         "f_pitch": 125, "iterm_relax_type": 1, "simplified_pids_mode": 2,
                         "simplified_gyro_filter": 1, "simplified_dterm_filter": 1,
                         "gyro_lpf1_dyn_min_hz": 250, "gyro_lpf1_dyn_max_hz": 500,
                         "dshot_bidir": 1, "rpm_filter_harmonics": 3, "blackbox_high_resolution": 0},
              "firmware": "4.5.2", "board": "SYNTHETIC", "profile": 0,
              "motor_output_bounds": [48, 2047], "acc_1g": 2048}
    return frame, units, config


@pytest.fixture
def measured(flight):
    frame, units, snapshot = flight
    report, _ = analyze(frame, units, snapshot, {"name": "synthetic.csv", "sha256": "a" * 64},
                        metadata={"airframe_id": "synthetic", "props": "test", "battery_cells": 6, "flight_mode": "ACRO"})
    return report
