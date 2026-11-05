---
name: fpv-drone-tuning
description: Review Betaflight FPV blackbox logs and generate evidence-backed PID and filter proposals, with three actual flight checks by default or a complete single-log review when requested.
---

# FPV Drone Tuning

Review PID, D-min/D Max, Feedforward, gyro/D-term LPF1/LPF2, RPM filtering, dynamic/static notches, TPA, I-term Relax, Anti-gravity and throttle controls together. Propose supported changes and mark the rest as hold or needs evidence; changing every setting is not a goal.

Read [references/evidence.md](references/evidence.md) before interpreting measurements. Use the shared `fpv-tune` Python package installed from this repository. Raw logs require a user-supplied compatible decoder. Do not depend on the author's filesystem paths.

The installer records the local Python interpreter and module command in `scripts/runtime.json`. Prefer that interpreter for an installed skill. In a source checkout without this local file, use an environment with the declared dependencies. Never commit the local runtime file containing machine paths.

## Three Actual Flight Checks

1. Baseline: log, current configuration, build and symptoms; complete PID + filter proposal with differential/full/rollback CLI.
2. Recheck: a new flight after applying selected changes; compare actual settings and similar throttle/command windows, then retain, revise or revert.
3. Evaluation: a third log plus pilot feedback and motor temperatures; record improvements and remaining problems. Test further if needed.

Three is the default count, not forced separation of PID and filters. Respect requests for a single complete analysis. Reprocessing one log never counts as a new flight. Combined changes are allowed, with the resulting attribution limit stated.

```sh
fpv-tune start --session outputs/build --checks 3
fpv-tune inspect --log flight-1.bbl
fpv-tune analyze --log flight-1.bbl --decoder /path/to/blackbox_decode --session outputs/build --plots
```

Use a new log on the same session for each next check. For one check use `--out`. Inspect the largest-by-bytes default section, choose `--index` where appropriate, and trim takeoff/landing impacts.

## Evidence

Validate timing, units, gaps, decode errors and fields first. Use contiguous windows, never concatenate disconnected stable samples before an FFT. D-term RMS depends on current gains and has no universal safe threshold. RPM enable flags are not proof of healthy telemetry.

Body-Z acceleration is not earth-frame vertical motion. Diagnose throttle symptoms using event-aligned setpoint, gyro, PID, motor and throttle traces. Rate-tracking error or an inferred response alone does not determine a gain change. This engine does not claim a synthetic overshoot proves a D improvement; cross-check actions in PIDtoolbox/Blackbox Explorer when needed.

## Plans

Each `changes.json` entry needs `key`, `value`, a `reason`, and `evidence` paths present in `analysis.json`. Do not substitute defaults for unrecorded settings.

```sh
fpv-tune plan --analysis outputs/build/check-1/analysis.json --config dump.txt --profile 0 --changes changes.json --out outputs/plan
```

CLI profiles are zero-based. Match the configuration to the flight and select multi-profile dumps explicitly. Executable plans currently support a conservative Betaflight 4.5.2 vocabulary; other firmware is analysis-only.

Manual PID/LPF plans explicitly disable their corresponding simplified controls, and explain that mode change. Do not combine manual values and simplified multipliers. Deliver coverage, candidate/full/rollback CLI and missing-data limitations. Add `--include-save` when requested.

Generated settings remain candidates until flight-tested. The engine never opens a serial port. Do not publish private logs, GPS, craft identifiers, config snapshots or personal paths by default.
