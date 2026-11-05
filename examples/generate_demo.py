"""Generate synthetic, non-flight data for CLI demonstrations; not a tuning preset."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def generate(out: Path, duration=12, fs=2000) -> None:
    out.mkdir(parents=True, exist_ok=True)
    t = np.arange(duration * fs) / fs
    for check in (1, 2, 3):
        rng = np.random.default_rng(100 + check)
        frame = pd.DataFrame({"time (us)": t * 1e6,
                              "rcCommand[3]": 1320 + 40 * np.sin(2 * np.pi * 0.2 * t)})
        for idx in range(3):
            command = 150 * np.sin(2 * np.pi * (1 + 0.2 * idx) * t)
            frame[f"setpoint[{idx}] (deg/s)"] = command
            frame[f"gyroADC[{idx}] (deg/s)"] = command + (2.5 / check) * np.sin(2 * np.pi * 230 * t) + rng.normal(0, 0.2, len(t))
            frame[f"gyroUnfilt[{idx}]"] = command + 20 * np.sin(2 * np.pi * 230 * t)
            if idx < 2:
                frame[f"axisD[{idx}]"] = (4 / check) * np.sin(2 * np.pi * 230 * t)
        for idx in range(4):
            frame[f"motor[{idx}]"] = 700 + 10 * np.sin(2 * np.pi * 3 * t)
            frame[f"eRPM[{idx}]"] = 900
        frame.to_csv(out / f"flight-{check}.csv", index=False)
    (out / "dump.txt").write_text("\n".join([
        "# Betaflight / SYNTHETIC 4.5.2", "set gyro_lpf1_dyn_min_hz = 250", "set gyro_lpf1_dyn_max_hz = 500",
        "set gyro_lpf1_static_hz = 250", "set gyro_lpf2_static_hz = 500", "set gyro_lpf1_type = PT1",
        "set gyro_lpf2_type = PT1", "set simplified_gyro_filter = ON", "profile 0",
        "set p_roll = 40", "set p_pitch = 40", "set d_pitch = 44", "set d_min_pitch = 32",
        "set i_pitch = 70", "set f_pitch = 125", "set simplified_pids_mode = RPY",
        "set iterm_relax_type = SETPOINT", "set dterm_lpf1_static_hz = 75", "set dterm_lpf2_static_hz = 150",
        "set simplified_dterm_filter = ON", "",
    ]), encoding="utf-8")
    (out / "metadata.json").write_text(json.dumps({"airframe_id": "synthetic-example", "props": "synthetic",
                                                "battery_cells": 6, "flight_mode": "ACRO"}, indent=2), encoding="utf-8")
    (out / "changes.json").write_text(json.dumps({"changes": [{"key": "p_pitch", "value": 42,
        "reason": "Synthetic CLI test only; not a real tuning recommendation.",
        "evidence": ["axes.pitch.tracking.normalized_mae"]}]}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    generate(parser.parse_args().out)
