"""Measurements use aligned, contiguous windows; none directly imply a PID change."""

from __future__ import annotations

import math
from collections import defaultdict

import numpy as np
import pandas as pd
from scipy.signal import coherence, find_peaks, welch

from .io import InputError


AXES = ("roll", "pitch", "yaw")
BANDS = {"20_80": (20, 80), "80_180": (80, 180), "180_450": (180, 450), "450_900": (450, 900)}


def is_enabled(value) -> bool:
    return value in (1, "ON")


def normalize_rates(frame: pd.DataFrame, units: dict, snapshot: dict) -> tuple[pd.DataFrame, dict, list[str], bool]:
    frame, units = frame.copy(), dict(units)
    conversions = []
    version = snapshot.get("firmware") or ""
    high_resolution = snapshot.get("values", {}).get("blackbox_high_resolution")
    plain_betaflight = version.startswith("4.5.") and high_resolution in (0, "OFF")
    confirmed = True
    for idx in range(3):
        for prefix in ("gyroADC", "gyroUnfilt", "setpoint"):
            key = f"{prefix}[{idx}]"
            if key not in frame:
                if prefix == "setpoint":
                    confirmed = False
                continue
            unit = units.get(key)
            if unit == "rad/s":
                frame[key] = frame[key] * (180.0 / np.pi)
                units[key] = "deg/s"
                conversions.append(f"{key}: rad/s -> deg/s")
            elif prefix == "setpoint" and unit is None and plain_betaflight:
                units[key] = "deg/s"
                conversions.append(f"{key}: raw Betaflight 4.5 non-high-resolution rate -> deg/s")
            elif prefix == "setpoint" and unit != "deg/s":
                confirmed = False
                frame[key] = np.nan
    return frame, units, conversions, confirmed


def timebase(frame: pd.DataFrame, units: dict, explicit_unit: str | None = None) -> tuple[np.ndarray, dict]:
    if "time" not in frame:
        raise InputError("CSV needs a time column with units; sampling rate is never guessed.")
    unit = explicit_unit or units.get("time")
    factors = {"us": 1e-6, "ms": 1e-3, "s": 1.0}
    if unit not in factors:
        raise InputError("Time unit is missing or unsupported; use --time-unit us, ms or s.")
    seconds = frame["time"].to_numpy(dtype=float, copy=True) * factors[unit]
    if len(seconds) < 4 or not np.isfinite(seconds).all():
        raise InputError("Need at least four finite timestamps.")
    delta = np.diff(seconds)
    positive = delta[delta > 0]
    if not len(positive):
        raise InputError("No increasing timestamps.")
    nominal = float(np.median(positive))
    normal = delta[(delta > nominal * 0.5) & (delta < nominal * 1.5)]
    if not len(normal):
        raise InputError("No contiguous sampling intervals.")
    dt = float(np.mean(normal))
    rate = 1.0 / dt
    jitter = float(np.std(normal) / dt)
    gaps = (delta > nominal * 1.5) | (delta <= 0) | (delta < nominal * 0.5)
    return seconds - seconds[0], {
        "sample_rate_hz": rate, "duration_s": float(seconds[-1] - seconds[0]),
        "duplicates": int(np.sum(delta == 0)), "backwards": int(np.sum(delta < 0)),
        "gap_count": int(np.sum(gaps)), "interval_jitter_ratio": jitter,
        "nominal_interval_s": nominal, "time_unit": unit,
    }


def contiguous_runs(seconds: np.ndarray, valid: np.ndarray, nominal: float) -> list[tuple[int, int]]:
    runs = []
    start = None
    for i, good in enumerate(valid):
        connected = i == 0 or 0.5 * nominal < seconds[i] - seconds[i - 1] < 1.5 * nominal
        if not good or not connected:
            if start is not None:
                runs.append((start, i))
            start = i if good else None
        elif start is None:
            start = i
    if start is not None:
        runs.append((start, len(seconds)))
    return runs


def contiguous_windows(seconds: np.ndarray, valid: np.ndarray, nominal: float,
                       size: int) -> list[tuple[int, int]]:
    return [(i, i + size) for start, end in contiguous_runs(seconds, valid, nominal)
            for i in range(start, end - size + 1, size)]


def values(frame: pd.DataFrame, name: str) -> np.ndarray | None:
    return frame[name].to_numpy(dtype=float, copy=True) if name in frame else None


def band_rms(freq: np.ndarray, density: np.ndarray, nyquist: float) -> dict:
    result = {}
    for name, (low, high) in BANDS.items():
        if nyquist < high or len(freq) < 2:
            result[name] = None
            continue
        mask = (freq >= low) & (freq < high)
        # The sum of density * bin width preserves power of discrete tones at band edges.
        power = float(np.sum(density[mask]) * (freq[1] - freq[0]))
        result[name] = math.sqrt(max(power, 0.0))
    return result


def spectrum(signal: np.ndarray, seconds: np.ndarray, timing: dict,
             windows: list[tuple[int, int]], unit: str) -> tuple[dict, np.ndarray, np.ndarray]:
    fs = timing["sample_rate_hz"]
    densities = []
    accepted = []
    freq = np.array([])
    for start, end in windows:
        piece = signal[start:end]
        if not np.isfinite(piece).all():
            continue
        freq, power = welch(piece, fs=fs, window="hann", nperseg=len(piece), detrend="constant")
        densities.append(power)
        accepted.append((start, end))
    if not densities:
        return {"status": "insufficient_contiguous_data", "unit": unit, "windows": 0}, freq, np.array([])
    density = np.mean(densities, axis=0)
    rms = band_rms(freq, density, fs / 2)
    mask = (freq >= 60) & (freq <= min(900, fs / 2))
    indices, _ = find_peaks(density)
    indices = [int(i) for i in indices if mask[i]]
    indices = sorted(indices, key=lambda i: density[i], reverse=True)[:3]
    return {"status": "measured", "unit": unit, "windows": len(accepted),
            "duration_s": sum((end - start) / fs for start, end in accepted), "band_rms": rms,
            "peaks_hz": [float(freq[i]) for i in indices]}, freq, density


def window_descriptors(frame: pd.DataFrame, windows: list[tuple[int, int]], seconds: np.ndarray) -> list[dict]:
    throttle = values(frame, "rcCommand[3]")
    setpoints = [values(frame, f"setpoint[{idx}]") for idx in range(3)]
    result = []
    for start, end in windows:
        thr = float(np.median(throttle[start:end])) if throttle is not None else None
        known_commands = all(sp is not None and np.isfinite(sp[start:end]).all() for sp in setpoints)
        excitation = max(float(np.sqrt(np.mean(sp[start:end] ** 2))) for sp in setpoints) if known_commands else None
        sp_peak = max((float(np.max(np.abs(sp[start:end]))) for sp in setpoints if sp is not None), default=math.inf)
        throttle_bin = int(np.clip((thr - 1000) // 200, 0, 4)) if thr is not None and math.isfinite(thr) else None
        demand_bin = 0 if excitation is not None and excitation < 40 else 1 if excitation is not None and excitation < 150 else 2 if excitation is not None else None
        result.append({"start_s": float(seconds[start]), "end_s": float(seconds[end - 1]),
                       "throttle_bin": throttle_bin, "setpoint_bin": demand_bin,
                       "throttle_median": thr, "setpoint_rms": excitation,
                       "low_setpoint": all(sp is not None for sp in setpoints) and sp_peak < 50
                       and thr is not None and 1100 < thr < 1750, "metrics": {}})
    return result


def tracking(frame: pd.DataFrame, idx: int, windows: list[tuple[int, int]]) -> dict:
    sp, gyro = values(frame, f"setpoint[{idx}]"), values(frame, f"gyroADC[{idx}]")
    if sp is None or gyro is None:
        return {"status": "missing_setpoint_or_gyro"}
    errors, magnitudes = [], []
    for start, end in windows:
        x, y = sp[start:end], gyro[start:end]
        active = np.isfinite(x) & np.isfinite(y) & (np.abs(x) >= 80)
        if active.any():
            errors.extend(np.abs(x[active] - y[active]))
            magnitudes.extend(np.abs(x[active]))
    if len(errors) < 200:
        return {"status": "insufficient_excitation", "active_samples": len(errors)}
    return {"status": "measured", "active_samples": len(errors),
            "mae_deg_s": float(np.mean(errors)),
            "normalized_mae": float(np.mean(errors) / np.mean(magnitudes)),
            "interpretation": "observed rate-tracking error; not a direct P/I/FF prescription"}


def response_diagnostic(frame: pd.DataFrame, idx: int, timing: dict,
                        seconds: np.ndarray) -> dict:
    sp, gyro = values(frame, f"setpoint[{idx}]"), values(frame, f"gyroADC[{idx}]")
    if sp is None or gyro is None:
        return {"status": "missing_signals"}
    size = max(256, round(timing["sample_rate_hz"] * 2))
    windows = contiguous_windows(seconds, np.isfinite(sp) & np.isfinite(gyro), timing["nominal_interval_s"], size)
    supported = []
    excited = 0
    for start, end in windows:
        if np.std(sp[start:end]) < 20:
            continue
        excited += 1
        freq, coh = coherence(sp[start:end], gyro[start:end], fs=timing["sample_rate_hz"], nperseg=size // 4)
        _, power = welch(sp[start:end], fs=timing["sample_rate_hz"], nperseg=size // 4)
        mask = (freq >= 3) & (freq <= 15) & (power > power.max() * 0.01) & np.isfinite(coh)
        if mask.any():
            supported.append(float(np.mean(coh[mask])))
    return {"status": "diagnostic_only", "excited_windows": excited,
            "mean_coherence_3_15hz": float(np.mean(supported)) if supported else None,
            "overshoot_percent": None,
            "interpretation": "No tail-normalized synthetic step response or automatic D increase; cross-check in PIDtoolbox and time traces."}


def motor_metrics(frame: pd.DataFrame, bounds: list | None, windows: list[tuple[int, int]]) -> dict:
    columns = [f"motor[{idx}]" for idx in range(4)]
    if not all(column in frame for column in columns):
        return {"status": "missing_motor_fields"}
    if not bounds or not all(isinstance(v, (int, float)) for v in bounds) or bounds[1] <= bounds[0]:
        return {"status": "unknown_output_scale", "high_saturation_percent": None}
    samples = []
    for start, end in windows:
        piece = frame[columns].iloc[start:end].to_numpy(dtype=float)
        if np.isfinite(piece).all():
            samples.append(piece)
    if not samples:
        return {"status": "insufficient_data"}
    normalized = (np.concatenate(samples) - bounds[0]) / (bounds[1] - bounds[0])
    return {"status": "measured", "bounds_source": "blackbox_motorOutput",
            "high_saturation_percent": float(np.mean(np.max(normalized, axis=1) >= 0.97) * 100),
            "low_saturation_percent": float(np.mean(np.min(normalized, axis=1) <= 0.03) * 100),
            "interpretation": "near-output-limit samples, not proof of desync or a TPA fault"}


def rpm_metrics(frame: pd.DataFrame, config: dict) -> dict:
    result = {"configured_bidirectional": config.get("dshot_bidir"),
              "configured_harmonics": config.get("rpm_filter_harmonics"),
              "telemetry_error_rate": None, "motors": {},
              "interpretation": "enabled settings do not establish healthy telemetry or filter effectiveness"}
    for idx in range(4):
        signal = values(frame, f"eRPM[{idx}]")
        if signal is not None:
            result["motors"][str(idx)] = {"finite_fraction": float(np.mean(np.isfinite(signal))),
                "positive_fraction": float(np.mean(np.isfinite(signal) & (signal > 0)))}
    return result


def throttle_events(frame: pd.DataFrame, seconds: np.ndarray, timing: dict, acc_1g) -> dict:
    thr = values(frame, "rcCommand[3]")
    if thr is None:
        return {"status": "missing_throttle", "events": []}
    fs, nominal = timing["sample_rate_hz"], timing["nominal_interval_s"]
    lookback, after = max(1, round(fs * 0.1)), max(2, round(fs * 0.5))
    events = []
    for start, end in contiguous_runs(seconds, np.isfinite(thr), nominal):
        segment = thr[start:end]
        if len(segment) <= lookback + after:
            continue
        delta = np.zeros(len(segment))
        delta[lookback:] = segment[lookback:] - segment[:-lookback]
        peaks, _ = find_peaks(delta, height=120, distance=max(1, round(fs)))
        for offset in peaks:
            i = start + int(offset)
            if offset < lookback or i + after >= end:
                continue
            change = float(thr[i + lookback] - thr[i - lookback])
            if change < 120:
                continue
            result = {"time_s": float(seconds[i]), "throttle_delta": change,
                      "throttle_before": float(thr[i - lookback]), "attitude_command_rms": None}
            demands = [values(frame, f"setpoint[{idx}]") for idx in range(3)]
            if all(signal is not None and np.isfinite(signal[i - lookback:i + after]).all() for signal in demands):
                result["attitude_command_rms"] = max(float(np.sqrt(np.mean(signal[i - lookback:i + after] ** 2))) for signal in demands)
            acc = values(frame, "accSmooth[2]")
            result["body_z_acc_rms_g"] = None
            if isinstance(acc_1g, (int, float)) and acc_1g > 0 and acc is not None:
                piece = acc[i:i + after]
                if np.isfinite(piece).all():
                    result["body_z_acc_rms_g"] = float(np.std(piece / acc_1g))
            events.append(result)
    return {"status": "observed", "events": events,
            "interpretation": "Body-frame Z acceleration contains tilt, thrust changes and vibration. It is not earth-frame vertical motion or altitude hold."}


def analyze(frame: pd.DataFrame, units: dict, snapshot: dict, source: dict,
            time_unit: str | None = None, window_seconds: float = 1.0, metadata: dict | None = None,
            trim: tuple[float, float] | None = None) -> tuple[dict, dict]:
    frame, units, conversions, setpoint_confirmed = normalize_rates(frame, units, snapshot)
    seconds, timing = timebase(frame, units, time_unit)
    if trim:
        mask = (seconds >= trim[0]) & (seconds <= trim[1])
        frame = frame.loc[mask].reset_index(drop=True)
        seconds = seconds[mask]
        if len(seconds) < 4:
            raise InputError("Selected time range is too short.")
        seconds = seconds - seconds[0]
        _, timing = timebase(frame, units, time_unit)
    config = snapshot.get("values", {})
    warnings = []
    blockers = []
    if timing["duplicates"] or timing["backwards"]:
        blockers.append("non_monotonic_timestamps")
    if timing["interval_jitter_ratio"] > 0.05:
        blockers.append("sampling_jitter_exceeds_5_percent")
    if source.get("decoder", {}).get("failed_frames", 0):
        warnings.append("Decoder reported failed frames; windows spanning time gaps are excluded.")
    if source.get("decoder", {}).get("failed_frames", 0) and source["decoder"]["failed_frames"] > 10:
        blockers.append("decoder_errors_need_review")
    if timing["sample_rate_hz"] < 1000:
        warnings.append("Log rate below 1 kHz limits high-frequency filter diagnostics.")
    if is_enabled(config.get("blackbox_high_resolution", 0)):
        blockers.append("high_resolution_signal_scaling_not_validated")
    if not setpoint_confirmed:
        blockers.append("setpoint_units_or_fields_unconfirmed")
    if not 0.5 <= window_seconds <= 4:
        raise InputError("--window-seconds must be between 0.5 and 4 seconds.")
    size = max(128, round(timing["sample_rate_hz"] * window_seconds))
    valid = np.ones(len(frame), dtype=bool)
    required = [f"gyroADC[{idx}]" for idx in range(3)]
    for name in required:
        if name not in frame:
            blockers.append(f"missing_{name}")
        else:
            valid &= np.isfinite(values(frame, name))
    gyro_units_known = all(units.get(name) == "deg/s" for name in required)
    if not gyro_units_known:
        blockers.append("gyro_units_must_be_explicit_deg_per_second")
    if "rcCommand[3]" in frame:
        valid &= np.isfinite(values(frame, "rcCommand[3]"))
        # This is an analysis selection criterion; it is not an arming/takeoff detector.
        valid &= values(frame, "rcCommand[3]") > 1050
    else:
        warnings.append("Throttle field is missing; bench/ground periods cannot be excluded by throttle.")
    windows = contiguous_windows(seconds, valid, timing["nominal_interval_s"], size)
    if len(windows) < 5:
        blockers.append("fewer_than_five_contiguous_flight_windows")
    descriptors = window_descriptors(frame, windows, seconds)
    signals, plots = {}, {}
    for idx, axis in enumerate(AXES):
        signals[axis] = {"tracking": tracking(frame, idx, windows),
                         "response": response_diagnostic(frame, idx, timing, seconds)}
        plots[axis] = {}
        for kind, name in (("gyro_post", f"gyroADC[{idx}]"), ("gyro_pre", f"gyroUnfilt[{idx}]"), ("dterm", f"axisD[{idx}]")):
            signal = values(frame, name)
            if signal is None:
                signals[axis][kind] = {"status": "missing_field"}
                continue
            unit = units.get(name, "raw_logged_units" if kind == "gyro_pre" else "PID_output_units")
            summary, freq, density = spectrum(signal, seconds, timing, windows, unit)
            signals[axis][kind] = summary
            plots[axis][kind] = {"frequency": freq, "density": density, "unit": unit}
            for descriptor, window in zip(descriptors, windows):
                local, _, _ = spectrum(signal, seconds, timing, [window], unit)
                for band, value in local.get("band_rms", {}).items():
                    descriptor["metrics"][f"{axis}.{kind}.{band}"] = value
    low_windows = [win for win, desc in zip(windows, descriptors) if desc["low_setpoint"]]
    for idx, axis in enumerate(AXES):
        signal = values(frame, f"gyroADC[{idx}]")
        if signal is not None:
            signals[axis]["low_setpoint_gyro"], _, _ = spectrum(signal, seconds, timing, low_windows, "deg/s" if gyro_units_known else "unknown")
    groups = defaultdict(list)
    for desc in descriptors:
        if desc["throttle_bin"] is not None:
            groups[desc["throttle_bin"]].append(desc)
    throttle_summary = {str(key): {"windows": len(rows), "duration_s": len(rows) * size / timing["sample_rate_hz"]}
                        for key, rows in sorted(groups.items())}
    report = {"schema_version": 2, "source": source, "trim_s": list(trim) if trim else None,
              "config": snapshot, "timing": timing, "metadata": metadata or {},
              "units": units,
              "quality": {"planning_blockers": sorted(set(blockers)), "warnings": warnings,
                          "unit_conversions": conversions, "setpoint_units_confirmed": setpoint_confirmed,
                          "window_seconds": size / timing["sample_rate_hz"], "flight_windows": len(windows),
                          "low_setpoint_windows": len(low_windows)},
              "axes": signals, "motor": motor_metrics(frame, snapshot.get("motor_output_bounds"), windows),
              "rpm": rpm_metrics(frame, config), "throttle_coverage": throttle_summary,
              "throttle_events": throttle_events(frame, seconds, timing, 1.0 if units.get("accSmooth[2]") == "g" else snapshot.get("acc_1g") if units.get("accSmooth[2]") in (None, "raw") else None),
              "windows": descriptors,
              "interpretation": "Measurements and hypotheses only. No universal noise threshold or automatic gain/filter prescription."}
    return report, plots


def compare(before: dict, after: dict) -> dict:
    if before.get("schema_version") != 2 or after.get("schema_version") != 2:
        raise InputError("Comparison needs two version-2 analysis.json reports; re-analyze legacy reports.")
    if (before["source"]["sha256"], before.get("trim_s")) == (after["source"]["sha256"], after.get("trim_s")):
        raise InputError("Same log content and time range: this is not a new flight check.")
    warnings = []
    a_config, b_config = before["config"], after["config"]
    if a_config.get("firmware") != b_config.get("firmware"):
        raise InputError("Firmware differs; raw metrics are not directly comparable.")
    if a_config.get("board") != b_config.get("board"):
        raise InputError("Flight-controller board differs; do not attribute differences to this tune.")
    if a_config.get("board") is None:
        warnings.append("Controller board identity is unavailable in the exported CSV configuration.")
    if is_enabled(a_config.get("values", {}).get("blackbox_high_resolution", 0)) or is_enabled(b_config.get("values", {}).get("blackbox_high_resolution", 0)):
        raise InputError("High-resolution signal scaling is not validated for comparison.")
    if not before["quality"].get("setpoint_units_confirmed") or not after["quality"].get("setpoint_units_confirmed"):
        raise InputError("Setpoint units must be confirmed before matching command-demand windows.")
    for axis in AXES:
        for signal in ("gyro_pre", "gyro_post", "dterm"):
            left_unit = before["axes"][axis].get(signal, {}).get("unit")
            right_unit = after["axes"][axis].get(signal, {}).get("unit")
            if left_unit != right_unit:
                raise InputError(f"Signal units differ: {axis} {signal}.")
    if before["quality"]["planning_blockers"] or after["quality"]["planning_blockers"]:
        warnings.append("At least one log has quality blockers; comparison is diagnostic only.")
    if abs(before["quality"]["window_seconds"] - after["quality"]["window_seconds"]) > 0.05:
        raise InputError("Use the same --window-seconds for both logs.")
    for field in ("airframe_id", "props", "battery_cells", "flight_mode"):
        left, right = before.get("metadata", {}).get(field), after.get("metadata", {}).get(field)
        if left is None or right is None:
            warnings.append(f"Missing matched flight metadata: {field}.")
        elif left != right:
            raise InputError(f"Flight metadata differs: {field}; not a comparable hardware/mode setup.")
    strata = []
    for throttle_bin in range(5):
        for demand_bin in range(3):
            left = [w for w in before["windows"] if (w["throttle_bin"], w["setpoint_bin"]) == (throttle_bin, demand_bin)]
            right = [w for w in after["windows"] if (w["throttle_bin"], w["setpoint_bin"]) == (throttle_bin, demand_bin)]
            if min(len(left), len(right)) < 3:
                continue
            metrics = {}
            keys = set(left[0]["metrics"]) & set(right[0]["metrics"])
            for key in sorted(keys):
                left_values = [w["metrics"].get(key) for w in left]
                right_values = [w["metrics"].get(key) for w in right]
                left_values = [v for v in left_values if v is not None]
                right_values = [v for v in right_values if v is not None]
                if min(len(left_values), len(right_values)) < 3:
                    continue
                a, b = float(np.median(left_values)), float(np.median(right_values))
                metrics[key] = {"before_median": a, "after_median": b,
                                "observed_change_percent": (b - a) / a * 100 if abs(a) > 1e-9 else None}
            strata.append({"throttle_bin": throttle_bin, "setpoint_bin": demand_bin,
                           "before_windows": len(left), "after_windows": len(right), "metrics": metrics})
    if not strata:
        warnings.append("No common throttle/command strata with at least three windows per flight.")
    changed = {key: {"before": a_config["values"].get(key), "after": b_config["values"].get(key)}
               for key in sorted(a_config["values"].keys() | b_config["values"].keys())
               if a_config["values"].get(key) != b_config["values"].get(key)}
    return {"schema_version": 2, "classification": "observational_not_causal",
            "before_sha256": before["source"]["sha256"], "after_sha256": after["source"]["sha256"],
            "common_strata": strata, "config_changes": changed, "warnings": warnings,
            "interpretation": "Matched throttle/command bins reduce a confound; they do not match wind, maneuvers, motor temperature or prove a parameter caused a change."}
