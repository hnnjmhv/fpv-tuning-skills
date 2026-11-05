# Three Checks: Baseline to Evaluation

[中文](workflow.md)

## Check 1: Full Baseline and Combined Proposal

Collect the original log, active PID-profile snapshot, build/props/battery/mass, and a symptom time or maneuver. Select a suitable flight section and check decoding, timing, fields, units, modes and bandwidth. Unfiltered gyro can already be aliased by logging subsampling; it is not full-bandwidth live sensor data.

Review P/I/D, dynamic D, FF, both gyro/D-term low-passes, RPM/dynamic/static notches, TPA, I-term Relax, Anti-gravity and throttle settings together. Mark each as candidate change, hold, or needs evidence. Do not change healthy values merely to make the table look tuned.

Combined PID and filter proposals are supported. Record a reason, actual evidence and applicable conditions for each change; generate full, differential and rollback CLI. A short verification flight is an operator check, not a program-certified pass.

## Check 2: Review a New Flight

Confirm the settings actually applied, then add a new log to the same session. Match hardware and mode, and compare contiguous windows under similar throttle/command demand. Inspect tracking, D noise, output headroom, RPM coverage and symptom events. Record changes in props, batteries, load, wind and maneuvers.

Keep changes only when supported. Unclear improvement or regression can justify partial or complete rollback. If multiple parameter families changed together, report an observational result for the package rather than attributing it uniquely to one parameter.

## Check 3: Evaluation and Remaining Issues

Use a third log after the revision, independent maneuvers, intended-use segments, motor temperatures and pilot feedback. Mark each requirement pass, fail or not covered. Improvement should recur in the relevant operating conditions; absence of high-throttle/stops/propwash coverage must be recorded.

The journal ends at `checks_analyzed_review_required`, not tuned. The skill explains evaluation evidence and unresolved issues. Remaining problems require a follow-up session.

## Context File

Unknown fields can be null or omitted:

```json
{
  "airframe_id": "my-build",
  "props": "actual-prop-model",
  "battery_cells": 6,
  "flight_mode": "ACRO",
  "mass_g": 650,
  "motor_temperature_c": null,
  "wind_notes": "record actual conditions"
}
```

No temperature measurement means no thermal pass claim. Context identifiers remain local by default.

```sh
fpv-tune start --session outputs/my-build --checks 3
fpv-tune analyze --log flight-1.bbl --decoder /path/to/blackbox_decode --session outputs/my-build --metadata context-1.json --symptom "throttle wobble" --plots
fpv-tune plan --analysis outputs/my-build/check-1/analysis.json --config dump-1.txt --profile 0 --changes changes-1.json --out outputs/plan-1
fpv-tune analyze --log flight-2.bbl --decoder /path/to/blackbox_decode --session outputs/my-build --metadata context-2.json --plots
fpv-tune plan --analysis outputs/my-build/check-2/analysis.json --config dump-2.txt --profile 0 --changes changes-2.json --out outputs/plan-2
fpv-tune analyze --log flight-3.bbl --decoder /path/to/blackbox_decode --session outputs/my-build --metadata context-3.json --plots
```

Commands only process local files. Operators apply CLI and fly. `--include-save` includes a save command when wanted, but never connects to an FC.
