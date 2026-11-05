# Assessment of the Original Project

[中文](assessment.md)

The original was a useful offline prototype: it found a decoder CLI, read some headers, calculated spectra and emitted settings. Its measurements and automatic decisions were too tightly coupled to justify a claim of fully automatic PID/filter tuning.

Material defects included FFTs over concatenated disconnected samples, a guessed 1 kHz fallback rate, permissive signal-role fallbacks, forced unit-tail normalization of inferred step responses, fixed low coherence/RMS thresholds, motor-scale guessing, flattened multi-profile configuration, and incorrect enum conversion. `iterm_relax_type=1` is SETPOINT in Betaflight 4.5.2, not GYRO.

The comparisons also overreached: different free-flight maneuvers cannot establish parameter causation, and body-Z acceleration is not earth-frame vertical motion. Historical claims that a 38%-to-5.7% inferred overshoot proved a D improvement, or that a 33% body-Z change proved the gyro filter was too open, exceeded the available evidence. Those numeric proposals remain unvalidated candidates, not public presets.

The replacement uses contiguous-window spectra, explicit timing/units, header-based motor limits, scoped profiles, versioned enums, observable RPM field coverage, and throttle/command-stratified comparisons. It retains diagnostic coherence but does not turn normalized synthetic overshoot into gain recommendations. Measurement and reviewed plan compilation are separate operations.

The release provides two language entrypoints sharing one engine, three actual flight checks by default, joint PID/filter reviews on every check, traceable candidate/full/rollback configurations, and an explicit not-flight-validated state. Tests and CI validate software behavior, not a particular airframe tune. No private logs, GPS, personal configuration or upstream executables belong in the release.

See [primary research](research.en.md) and [measurement methodology](methodology.md).
