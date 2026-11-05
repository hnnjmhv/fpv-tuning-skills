# Evidence and Version Boundaries

Validate names, ranges and lookup enums against [Betaflight 4.5.2 settings.c](https://github.com/betaflight/betaflight/blob/4.5.2/src/main/cli/settings.c). Use [pid.c](https://github.com/betaflight/betaflight/blob/4.5.2/src/main/flight/pid.c) for PID/TPA/Anti-gravity behavior and [blackbox.c](https://github.com/betaflight/betaflight/blob/4.5.2/src/main/blackbox/blackbox.c) for logged fields.

`iterm_relax_type` maps GYRO=0 and SETPOINT=1. Keep simplified controls consistent with manual values. GUI D Max corresponds to `d_*`; interpret base D / D-min with the actual firmware version.

The [official RPM guide](https://betaflight.com/docs/wiki/guides/current/DSHOT-RPM-Filtering) and [4.5 release notes](https://betaflight.com/docs/wiki/release/Betaflight-4-5-Release-Notes) supply context, not permission to copy settings from another version.

Use [PIDtoolbox](https://github.com/bw1129/PIDtoolbox) for independent spectrum/response checks and [Blackbox Explorer](https://github.com/betaflight/blackbox-log-viewer) for individual time traces. Coherence is a diagnostic, not a universal reliability threshold or a direct gain rule.

Throttle/command strata reduce some comparison confounds but do not control props, battery, mass, flight mode, wind and maneuvers. Body Z acceleration requires an attitude transform before interpreting earth-frame vertical motion; absent that transform, do not claim altitude oscillation.

Repository `docs/research.en.md` contains topic-by-topic primary references. `docs/workflow.en.md` explains the three-check protocol. These extended documents are optional during installed-skill use; the necessary constraints and direct sources are provided here.
