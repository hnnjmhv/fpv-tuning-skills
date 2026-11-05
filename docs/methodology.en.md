# Measurement Contract

[中文 / bilingual notes](methodology.md)

## Timing and Windows

Time units must be explicit. Positive normal intervals estimate logging rate. Duplicate or backward timestamps block planning. Intervals over 1.5 times or under 0.5 times the nominal interval split windows. Interval jitter above 5% and fewer than five accepted windows also block compilation. These are implementation quality gates, not official tuning or flight-safety thresholds.

Spectra use complete contiguous windows, one second by default and configurable from 0.5 to 4 seconds. Effective duration, rate, usable-window count and gaps remain in the report. The `rcCommand[3] > 1050` selection reduces ground data but does not prove arming or flight. Low-setpoint requires all three commands below 50 deg/s and throttle 1100–1750 throughout a window; it is not proof of steady hover. Inspect flight modes and trim impacts separately.

## Spectra

Use SciPy Welch PSD with a Hann window and constant detrending within each continuous window. Average densities, then sum discrete bin power within complete 20–80, 80–180, 180–450 and 450–900 Hz bands. A band beyond log Nyquist is unavailable rather than zero. FFT processing cannot undo acquisition aliasing.

PSD uses squared-signal-units per Hz. Post-gyro must have a confirmed angular-rate scale; labelled rad/s is converted to deg/s. Unlabelled pre-gyro stays in raw logged units, without an undocumented pre/post attenuation ratio. D-term is gain/TPA-dependent control output, shown on a separate panel. [SciPy Welch definition](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.welch.html)

## Tracking and Response

Aligned rate error is measured for command magnitude at least 80 deg/s with at least 200 active samples. These are reporting selections, not universal good/bad thresholds. Setpoint units must be labelled or established from the confirmed non-high-resolution Betaflight format. Missing or unknown units block executable plans.

Coherence is diagnostic only. The engine does not force a deconvolved tail to one or generate D increases from inferred overshoot. High-resolution scaling currently lacks a golden-reference validation and blocks executable plans and quantitative comparisons rather than risking double conversion.

## Comparison

Compare medians in common throttle bins, each 200 command units wide, and command-RMS bins below 40, 40–150 and at least 150 deg/s. Require at least three windows in each flight for a common stratum. This controls only some confounds; it establishes neither causality nor a confidence interval across independent flights.

Known firmware, controller, props, battery-cell or flight-mode differences reject direct comparisons. Missing context is reported. D-term changes describe observed output, not gain-independent filter attenuation. Body-frame Z acceleration includes thrust and attitude effects and is not earth-frame vertical motion.

## Configuration Plans

The executable 4.5.2 vocabulary is a conservative subset, not a full CLI specification. It validates keys, types, lookup enums, supported ranges, profile identity and cross-parameter bounds. This does not validate a tuning decision. Proposed values require a rationale and existing non-null analysis paths. Match the current snapshot to the flight and choose an explicit zero-based profile.

Full CLI contains recorded supported values only. Unknown entries become `needs_data` and are omitted rather than defaulted. Manual PID or LPF values disable their respective simplified controllers, with the reason stated; rollback restores prior modes and values. No serial write transport is included.

Plan status stays `candidate_not_flight_validated`. The third journal entry stays `checks_analyzed_review_required` and includes a criterion-by-criterion evaluation template. Only new flight evidence and operator assessment can support acceptance.
