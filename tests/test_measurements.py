from copy import deepcopy

import numpy as np
import pytest

from fpv_tune.analysis import analyze, compare, contiguous_windows, spectrum, timebase
from fpv_tune.io import InputError


def test_microseconds_and_seconds_agree(flight):
    frame, units, _ = flight
    _, micro = timebase(frame, units)
    converted = frame.copy()
    converted["time"] /= 1e6
    _, seconds = timebase(converted, {"time": "s"})
    assert micro["sample_rate_hz"] == pytest.approx(2000)
    assert seconds["sample_rate_hz"] == pytest.approx(micro["sample_rate_hz"])


def test_missing_time_unit_is_not_guessed(flight):
    with pytest.raises(InputError, match="Time unit"):
        timebase(flight[0], {})


def test_nan_and_timestamp_gaps_do_not_get_concatenated():
    seconds = np.concatenate((np.arange(6) / 1000, 1 + np.arange(6) / 1000))
    windows = contiguous_windows(seconds, np.ones(12, dtype=bool), 0.001, 4)
    assert windows == [(0, 4), (6, 10)]
    mask = np.ones(12, dtype=bool)
    mask[2] = False
    assert all(not (start <= 2 < end) for start, end in contiguous_windows(seconds, mask, 0.001, 4))


def test_spectrum_rms_recovers_tone(flight):
    frame, units, _ = flight
    seconds, timing = timebase(frame, units)
    signal = 2 * np.sin(2 * np.pi * 230 * seconds)
    windows = contiguous_windows(seconds, np.ones(len(frame), dtype=bool), timing["nominal_interval_s"], 2000)
    metric, _, _ = spectrum(signal, seconds, timing, windows, "deg/s")
    assert metric["band_rms"]["180_450"] == pytest.approx(np.sqrt(2), rel=0.01)
    assert metric["peaks_hz"][0] == pytest.approx(230, abs=1)


def test_nyquist_limit_is_unknown_not_zero(flight):
    frame, units, _ = flight
    frame = frame.iloc[::4].reset_index(drop=True)
    seconds, timing = timebase(frame, units)
    metric, _, _ = spectrum(frame["gyroADC[0]"].to_numpy(), seconds, timing, [(0, 500)], "deg/s")
    assert metric["band_rms"]["180_450"] is None


def test_motor_bounds_use_header_even_with_low_throttle(measured):
    assert measured["motor"]["high_saturation_percent"] == 0
    assert measured["motor"]["low_saturation_percent"] == 0


def test_unknown_motor_bounds_not_inferred_from_peak(flight):
    frame, units, snapshot = flight
    snapshot = deepcopy(snapshot)
    snapshot["motor_output_bounds"] = None
    report, _ = analyze(frame, units, snapshot, {"sha256": "b", "name": "test"})
    assert report["motor"]["status"] == "unknown_output_scale"
    assert report["motor"]["high_saturation_percent"] is None


def test_rpm_flags_not_equated_to_error_free_telemetry(measured):
    assert measured["rpm"]["configured_bidirectional"] == 1
    assert measured["rpm"]["telemetry_error_rate"] is None
    assert measured["rpm"]["motors"]["0"]["positive_fraction"] == 1


def test_no_synthetic_overshoot_claim(measured):
    assert measured["axes"]["pitch"]["response"]["overshoot_percent"] is None
    assert measured["axes"]["pitch"]["response"]["status"] == "diagnostic_only"


def test_same_content_cannot_be_a_follow_up(measured):
    with pytest.raises(InputError, match="Same log"):
        compare(measured, deepcopy(measured))


def test_unmatched_maneuvers_do_not_produce_percentages(measured):
    other = deepcopy(measured)
    other["source"]["sha256"] = "b" * 64
    for window in other["windows"]:
        window["throttle_bin"] = 4
    result = compare(measured, other)
    assert result["common_strata"] == []
    assert result["warnings"]


def test_comparison_is_observational_and_uses_matched_bins(measured):
    other = deepcopy(measured)
    other["source"]["sha256"] = "b" * 64
    for window in other["windows"]:
        for key, value in window["metrics"].items():
            if value is not None:
                window["metrics"][key] = 2 * value
    result = compare(measured, other)
    assert result["classification"] == "observational_not_causal"
    assert result["common_strata"]
    metric = result["common_strata"][0]["metrics"]["roll.gyro_post.180_450"]
    assert metric["observed_change_percent"] == pytest.approx(100)


def test_comparison_rejects_changed_hardware(measured):
    other = deepcopy(measured)
    other["source"]["sha256"] = "b" * 64
    other["metadata"]["props"] = "different"
    with pytest.raises(InputError, match="props"):
        compare(measured, other)


def test_comparison_rejects_signal_scale_change(measured):
    other = deepcopy(measured)
    other["source"]["sha256"] = "b" * 64
    other["axes"]["roll"]["gyro_pre"]["unit"] = "deg/s"
    with pytest.raises(InputError, match="units differ"):
        compare(measured, other)


def test_non_monotonic_time_blocks_plan(flight):
    frame, units, snapshot = flight
    frame = frame.copy()
    frame.loc[100, "time"] = frame.loc[99, "time"]
    report, _ = analyze(frame, units, snapshot, {"sha256": "b", "name": "test"})
    assert "non_monotonic_timestamps" in report["quality"]["planning_blockers"]


def test_zero_gyro_response_has_no_nan_confidence(flight):
    import json
    frame, units, snapshot = flight
    frame = frame.copy()
    frame["gyroADC[0]"] = 0
    with np.errstate(invalid="ignore", divide="ignore"):
        report, _ = analyze(frame, units, snapshot, {"sha256": "b", "name": "test"})
    assert report["axes"]["roll"]["response"]["mean_coherence_3_15hz"] is None
    json.dumps(report, allow_nan=False)
