# FPV Betaflight Blackbox Tuning Research and Claim Audit

Retrieved and locally checked: **2026-11-05**. Chinese counterpart: `research.md`. Both documents carry the same conclusions, evidence identifiers, and limitations.

## 1. Scope and Evidence Rules

- **Firmware facts**: The primary baseline is Betaflight **4.5.2**, tag commit `024f8e13d4e642eb6a380308685b9ea3aa3ef1a2`. The entire 4.x series is not treated as one implementation.[V45], [T45]
- **Current differences**: At retrieval, the official latest stable release was **2026.6.2**, published 2026-09-16, at commit `e0b7bb01b17b21351057e9ead2d1ab39dd44fa16`. "Current" means this retrieval snapshot, not master, prereleases, or future releases.[V26], [T26]
- **Source priority**: Actual FC version and complete configuration > matching tagged source > version-specific release notes > continuously updated official Wiki. C members, CLI names, GUI labels, and Blackbox headers are not interchangeable aliases.
- **Engineering decisions**: Segmentation, spectral estimation, quality gates, comparison statistics, and the three-flight workflow below are this skills repository's offline DSP and experimental-design decisions, not a Betaflight-mandated tuning procedure. SciPy/MathWorks documentation establishes algorithm definitions, not safe or optimal FC settings.
- This source-research stage did not decode user flight logs, connect to or modify an FC, conduct flights, or accept new software; main-project software regressions are recorded separately. There are no universal PID, cutoff, TPA, FF, or coherence-threshold presets here.

## 2. Claims to Keep, Rewrite, or Reject

| Claim under audit | Finding and publishable wording |
| --- | --- |
| "GYRO_SCALED must be enabled to inspect unfiltered gyro." | Rewrite. Version 4.5 added default unfiltered gyro logging; verify that the particular log actually contains `gyroUnfilt`. An older analyzer may still require the debug mode for compatibility, not because the firmware inherently requires it.[W45], [B1], [B3] |
| "gyroUnfilt is full-rate, completely unprocessed sensor ADC." | Reject. It comes from calibrated, aligned, scaled gyro data and is subsampled by logging. It is not a continuous full-rate observation unaffected by hardware filtering.[B2], [G1], [G3] |
| "Enabling bidirectional DShot/RPM settings proves RPM filtering works." | Reject. Configuration, valid per-motor telemetry, active notches, and spectral results are separate evidence levels.[R1], [R2], [R3] |
| "An RPM_FILTER debug trace proves the filter is enabled." | Reject. In 4.5.2 this debug is populated before the enabled-state check.[R1] |
| "LPF2 is unnecessary delay and should be disabled with RPM filtering." | Reject. Gyro LPF2 precedes gyro-to-PID downsampling; RPM notches follow it. Reducing filtering requires sampling, aliasing, and measured-noise evidence.[G2], [G3] |
| "d_roll is the calm-flight D baseline in 4.5.2." | Reject. In that version's CLI, `d_roll` is the dynamic D ceiling; `d_min_roll` is the baseline when dynamic D is active.[P1], [P2] |
| "Anti-Gravity only increases I / supplies anti-gravity lift." | Reject. Version 4.5.2 uses throttle changes to accelerate roll/pitch I integration and boost P. It is not an altitude or vertical-thrust controller.[A1], [A2], [A3], [P3] |
| "FF, feedforward_boost, and throttle_boost are the same boost." | Reject. The first two operate in the angular-rate command feedforward path; the last transiently boosts mixer throttle using a high-pass component.[F1], [F2], [M1] |
| "One bounce identifies a particular P, D, FF, or AG error." | Reject single-cause attribution. Check commands, I-term relax, telemetry, actuator headroom, mode, and maneuver conditions as well.[P2], [P3], [F1] |
| "Lower body-Z acceleration proves less earth-vertical shaking." | Reject. Body Z is not earth vertical; attitude, the gravity reference, translation, and rotational effects can all change the measurement.[ACC1], [ACC2] |
| "Coherence above one fixed value permits automatic PID tuning." | Reject. Coherence depends on frequency, excitation, and estimation conditions. These sources establish no threshold valid for all flights.[D2], [D3], [D5] |
| "Normalizing a deconvolved step tail to 1 proves zero steady-state error." | Reject. This can impose unit gain and hide low-frequency non-identifiability, truncation, and regularization bias. Preserve unnormalized results and an independent reference; see Section 7. |
| "Better scores on two free flights prove the settings caused improvement." | Reject. Unmatched maneuvers and conditions support association only. Changing PID and filters together also prevents attribution to one parameter. |
| "A new offline script is equivalent to PIDtoolbox." | Unsupported. The author's `PTstepcalc.m` was inaccessible in this research. Generic DSP capability, similar plots, or a third-party port do not establish algorithmic or numerical equivalence.[PT1], [PT2] |

## 3. Blackbox Fields, Types, Units, and Sampling Contract

### 3.1 Read the Actual Headers

For every log index in every file, separately read `Firmware revision`, board/build information, `Field I name/signed/predictor/encoding`, `I interval`, `P interval`, `looptime`, `pid_process_denom`, `gyro_scale`, `acc_1G`, `motorOutput`, `blackbox_high_resolution`, debug mode, and field-selection settings. Fields may be absent because of build options, missing sensors, zero D gains, or disabled logging groups. Missing is not measured zero.[B1], [B3], [B4]

"Integer" below refers to the signedness of the log protocol, not a fixed CSV column type. Firmware acquisition buffers use `int16_t` for gyro, setpoint, acceleration, and debug, and `int32_t` for PID components; encoding still follows the headers. `lrintf` shows that floating-point control values are quantized before logging. The differential codec's `AVERAGE_2` is a predictor, not an extra two-sample average applied to the physical signal.[B1], [B2], [B5]

### 3.2 Main 4.5.2 Analysis Fields

Let `h = 10` when `blackbox_high_resolution` is enabled, otherwise `h = 1`. These conversions apply to **decoded field values not already converted to physical units**. Do not divide again if a CSV exporter or GUI already converted them.[B2], [B6], [E1]

| Field | Type and physical meaning | Analysis constraints |
| --- | --- | --- |
| `time`, `loopIteration` | Unsigned integers; raw time is microseconds and iteration is the PID-loop index | Check monotonicity, wraparound, resets, missing frames, and duplicates; do not derive time from CSV row numbers.[B1], [B2] |
| `gyroADC[0..2]` | Signed integers; software-filtered roll/pitch/yaw angular rates, raw value divided by `h` in deg/s | The normal rate PID measurement, not attitude angles or raw ADC.[B2], [P3] |
| `gyroUnfilt[0..2]` | Signed integers; aligned/scaled angular rate before software filtering, raw value divided by `h` in deg/s | Logs capture selected instants, not necessarily every gyro sample.[B2], [G1] |
| `setpoint[0..2]` | Signed integers; angular-rate targets used by PID, raw value divided by `h` in deg/s | Prefer these for tracking comparisons over reconstructing rates from sticks; not raw receiver input.[B2], [P2] |
| `setpoint[3]` | Signed integer; `mixerGetThrottle()` multiplied by 1000 | Divide by 1000 for this logged throttle variable, or by 10 for percent; **not scaled by `h`**. Includes throttle limiting and throttle boost, but excludes subsequent thrust-linearization compensation, dynamic idle, and airmode.[B2], [M1] |
| `rcCommand[0..3]` | First three are signed, throttle is unsigned in the log encoding; processed control inputs | Not four deg/s columns. High resolution affects all four; the GUI also applies a center offset to the first three when displaying microseconds. Display values are not PID setpoints.[B1], [B2], [E1] |
| `axisP/I/D/F[axis]` | Signed integers; controller component outputs in firmware control units | Not GUI P/I/D/F gains, deg/s, or SI torque. `axisD` already includes dynamic D and TPA.[B2], [P2] |
| `motor[n]` | Unsigned log encoding; command sent to the motor-output path | Interpret with `motorOutput`, protocol, and mixer. Do not assume 1000..2000; it is neither RPM nor actual thrust. Reaching an endpoint only supports command-headroom analysis.[B1], [B2], [B4] |
| `eRPM[n]` | Unsigned log encoding; **electrical RPM / 100** | For magnetic pole count `p`, mechanical RPM = `raw * 100 / (p/2)`; divide again by 60 for mechanical Hz. First check whether the exporter converted the values and whether the pole count is real.[B1], [R2], [E1] |
| `accSmooth[0..2]` | Signed integers; aligned, calibrated, optionally low-pass-filtered body-frame accelerometer data | Raw value / `acc_1G` gives g; not gravity-removed earth-frame acceleration. The name does not guarantee an active LPF.[B2], [B4], [ACC1] |
| `debug[0..7]` | Signed integers; mode-specific internal signals | Verify channel count, axes, stages, and scales against the firmware version. Do not apply `h` or deg/s indiscriminately.[B1], [G3], [P2] |
| `vbatLatest`, `amperageLatest` | Unsigned voltage and signed current; usual 4.5.2 raw scales are 0.01 V and 0.01 A respectively | Verify calibration and sensor source. Exporters may already output V/A; avoid double conversion.[B2], [U1] |

Repeated writes of eRPM or acceleration in main frames do not mean that an ESC or sensor supplied a fresh sample at each timestamp. In particular, an invalid DShot packet in 4.5.2 does not update the valid value. A constant sequence may reflect stable speed or repeated/stale telemetry; nonzero values alone do not establish health.[R3], [ACC1]

Current 2026.6.2 retains the gyro/setpoint high-resolution rules, the thousandths scale of `setpoint[3]`, and the electrical-RPM/100 scale of eRPM. It can also conditionally log wing `axisS`, more general servo channels, and `imuQuaternion[0..2]`. The latter stores x/y/z components multiplied by 32767 after selecting a positive w, not three attitude angles. Do not read new fields by fixed 4.5.2 column positions. Even with an attitude quaternion, coordinate conventions, synchronization, and estimator validity must be checked before converting accSmooth to earth-frame linear acceleration.[B26], [B26F], [R26]

### 3.3 Subsampling and Aliasing

In 4.5.2, the usual logging interval is `N = 2^sample_rate` PID iterations. Nominal logging rate is approximately `f_PID / N`, not a fixed 1 kHz or 2 kHz; `f_PID` depends on gyro sampling and PID division. I-frames have their own schedule, and very low logging rates can produce I-frames only. Cross-check actual `time` differences, `loopIteration`, headers, and decoder missing-frame statistics.[B4], [B6], [B7]

Engineering requirement: report effective sample rate, interval distribution, gaps, continuous-segment duration, and analyzable bandwidth. Logging subsampling is not automatic anti-alias filtering; high-frequency content in `gyroUnfilt`/`GYRO_SCALED` can fold below log Nyquist. Interpolation, zero padding, or a larger FFT cannot recover bandwidth lost at acquisition.[B2], [G3], [D1], [D4]

`blackbox_decode --raw` skips predictor reconstruction and outputs field deltas; it does **not** mean "export unfiltered gyro." Record decoder version, complete command, and unit options; use ordinary reconstructed decoding and retain original BBL/BFL/TXT files plus decoding-error statistics.[U2]

## 4. Evidence for RPM and Filtering

### 4.1 RPM: Configuration Is Not Measurement

RPM-filter initialization in 4.5.2 requires available bidirectional DShot and nonzero harmonic count; zero-weight harmonics have no filtering effect. The conditions for logging `eRPM` instead check motor count, bidirectional telemetry enablement, and the RPM field setting, not fresh valid telemetry at every sample. `RPM_FILTER` debug is populated before the `isRpmFilterEnabled()` early return, so it also does not prove enablement.[R1], [B3]

Record four separate evidence levels:

1. Configuration/capability: motor protocol, bidirectional DShot, ESC firmware support, verified pole count, harmonics/weights/Q/minimum frequency/telemetry LPF, and build features.
2. Actual telemetry: per-motor speed, response to maneuvers, zero values/plateaus/jumps, and packet errors. Remove props for safe ground checks. The official `dshot_telemetry_info` command reports per-ESC packet success, but was not executed against an FC here.[WDEBUG], [WRPM]
3. Filter path: enabled in the actual version, sensible notch frequencies/weights, and known pre/post-filter observation stages.[R1], [G3]
4. Flight results: inspect residual motor harmonics, D noise, motor temperature, and related evidence under matched speed/operating conditions. Report "configured" separately from "effect verified."

The tagged source additionally shows that 4.5.2 sets `ARMING_DISABLED_DSHOT_TELEM` when bidirectional DShot is enabled without the required per-motor telemetry. Do not infer every version's exact diagnostic from an older guide's `RPMFILTER` wording, and do not bypass arming protection to complete tuning.[ARM45]

Motor-harmonic tracking does not eliminate every structural resonance, damaged prop, bearing fault, or broadband-noise source. Inspect mechanical condition first; do not use reduced filtering to conceal unknown hardware problems. This is a diagnostic boundary, not a universal notch-count recommendation.

### 4.2 Gyro LPF2's Anti-Alias Position

In 4.5.2, Gyro LPF2 is initialized and applied at the gyro **sampling rate**, before reduction to the PID rate. Without active LPF2, simple averaging is used. RPM filtering, static notches, Gyro LPF1, and dynamic notches follow. Version 2026.6.2 retains this LPF2/averaging downsampling path.[G1], [G2], [G3], [G26]

Thus "LPF2 serves an anti-alias role before PID downsampling" is an engineering interpretation of the actual path, not a guarantee that any cutoff is sufficient. Later RPM/notch filters cannot undo components already aliased. Do not confuse the sensor's internal hardware LPF, Gyro LPF2, D-term LPF2, and an offline resampling FIR.

Discuss specific filtering reductions only with the sampling relationship, filter type/order, pre/post spectra, D noise, CPU/missing-frame evidence, and motor thermal condition. The ordinary 4.5.2 `gyroADC` trace alone cannot identify one filter stage's attenuation or delay. `GYRO_SAMPLE` debug observes several stages but remains limited by the logging rate.[G3]

## 5. PID, Dynamic D, and Simplified Slider Semantics

### 5.1 A Rate Loop, Not a Vertical-Acceleration Loop

In normal Acro rate operation, P uses angular-rate error, I integrates an error modified by mechanisms such as relax, D uses the negative derivative of additionally filtered gyro, and F comes from command feedforward. Angle/Horizon, launch control, crash recovery, yaw-spin handling, and limits can change those relationships. Height loss or a body-Z spike cannot directly determine P/I/D.[P2], [P3]

### 5.2 Dynamic D Mapping

| Item | 4.5.2 | Current 2026.6.2 |
| --- | --- | --- |
| Baseline and ceiling | With active dynamic D, `d_min_roll/pitch/yaw` are baselines and `d_roll/pitch/yaw` are ceilings | `d_roll/pitch/yaw` are baselines; `d_max_roll/pitch/yaw` are ceilings |
| Activation | Baseline must be positive and below main D; otherwise fixed main D is used, not D disabled | Main D must be positive and d_max greater than main D for dynamic increases |
| Sensitivity CLI | **Already** `d_max_gain` and `d_max_advance`; C members are still `d_min_gain`/`d_min_advance` | CLI remains `d_max_gain` and `d_max_advance` |
| Internal calculation | Setpoint sensitivity includes the product of gain and advance | Gyro gain and setpoint advance independently control their respective channels; the old product interpretation is invalid |
| Simplified dynamic D CLI | `simplified_dmax_gain`, mapped to internal `simplified_dmin_ratio` | `simplified_d_max_gain` |
| Debug | `D_MIN`: [2]/[3] are active roll/pitch D gains multiplied by 10, populated only in the dynamic path | `D_MAX`: uses `gyro_debug_axis`; [2] is that axis's active D gain multiplied by 10, [3] the gain multiplier multiplied by 100 |

These comparisons use tagged initialization, calculations, and CLI mappings rather than mechanically applying the Wiki's historical table to 4.5.2.[P1], [P2], [N45], [C45], [P26], [I26], [N26], [S26]

Important limitation: The current official Dynamic D page still describes an early migration as `d_min_boost_gain -> d_max_gain` and describes D_MAX [2]/[3] as roll/pitch. This does not override the tagged source above. Its defaults are not measured configurations for every version/build. This research did not exhaustively establish all intermediate versions or exact rename dates.[WD]

In 4.5.2, `D_LPF` [0]/[1] use the negative angular-rate derivative **after gyro filtering but before D-specific filtering**, divided by 25. They are neither raw ADC nor outputs already multiplied by D gain. Channels [2]/[3] are D outputs after dynamic D, before TPA, multiplied by 10. Ordinary `axisD` is after TPA. Do not assign one common unit or scale and compare these channels directly.[P2], [DL45], [DLS45]

### 5.3 Simplified Modes and Coupled Sliders

`OFF` does not recalculate gains through simplified PID sliders; `RP` covers roll/pitch and `RPY` includes yaw. Simplified gyro and D-term filter switches exist independently of the PID mode; disabling PID simplification does not disable all filter sliders. Mode changes or slider application can overwrite axis gains; retain actual CLI values before and after.[S45], [C45], [WPID]

Version 4.5.2 recalculates sliders from **firmware default gains**, not relative adjustments to arbitrary manual values: master affects P/I/D/F, PI affects P/I, I further affects I, D affects baseline and ceiling, dynamic D changes the gap from baseline to ceiling, and pitch PI also affects pitch F. Filter multipliers scale cutoffs of enabled LPFs; larger generally means less filtering, not more, and does not automatically enable every disabled path.[S45]

Current dynamic D equations and CLI names differ. Copying slider numbers does not establish an identical controller. Reports should include mode, sliders, resulting raw gains, filter types/cutoffs, and firmware version together.[S26], [N26]

## 6. Anti-Gravity, FF, TPA, and Throttle Transients

### 6.1 Anti-Gravity

Version 4.5.2 starts from the absolute throttle derivative, weights it by throttle position and direction of change, and smooths it with PT2. `anti_gravity_cutoff_hz` affects peaks and duration. When enabled, `anti_gravity_gain` drives roll/pitch I-integration acceleration; `anti_gravity_p_gain` participates in extra P boost, attenuated at larger angular-rate targets. Yaw receives neither of these AG boosts.[A1], [A2], [A3], [P3]

AG therefore affects more than I and is not feedback from altitude, body Z, or "gravity magnitude." Attitude error during throttle changes can nominate AG as a candidate, but center of gravity, thrust headroom, voltage, I-term relax, mixing, and filtering must also be checked. Current 2026.6.2 retains this throttle-derivative input mechanism; that does not establish identical transients or defaults.[A26]

In 4.5.2 `ANTI_GRAVITY` debug, [0]/[1] are derivative quantities at different processing stages multiplied by 100, [2] is the I-boost ratio relative to pitch Ki multiplied by 1000, and [3] is the pitch P-boost ratio multiplied by 1000. These are not four accelerometer channels; do not copy a rolling debug summary blindly.[A1], [A2], [A3]

### 6.2 Feedforward

Version 4.5.2 FF uses changes in rate-curve-derived targets and RX timing, with duplicate-packet handling, smoothing, acceleration boost, center transition, averaging, jitter reduction, and limits near maximum rate. RC smoothing also applies PT3 to FF when present. Final F output is multiplied by the axis F coefficient. An offline finite difference of logged `setpoint` generally cannot reproduce this entire path sample by sample.[F1], [F2], [P2]

`feedforward_boost` adds an acceleration component of command change. In 4.5.2, `feedforward_max_rate_limit` limits same-direction FF according to remaining maximum-rate headroom; it is not simply a switch at a stick-travel percentage. Interpret FF noise, move-entry overshoot, and stopping bounce with actual RX packet rate, quantization, RC smoothing, and actuator limits.[F1]

The official Feed Forward 2.0 page explicitly introduces 4.1. Its old names and absolute claim that FF cannot cause oscillations are not universal causal rules for 4.5.2 or current firmware. Ideal feedforward does not directly change feedback poles, but RC noise, resonant excitation, saturation, and the pilot-in-the-loop can still produce shaking. This distinction is engineering interpretation, not an official safety guarantee.[WFF], [F1]

Current 2026.6.2 FF is refactored: roll/pitch boost is separate from the yaw path, which contains a hold component. Do not carry 4.5.2 yaw FF signatures or debug scales across unchanged.[F26]

### 6.3 TPA

In the normal 4.5.2 build path, `tpa_mode=D` attenuates D only and `PD` attenuates P/D, not all PID/FF terms proportionally. Builds without `USE_TPA_MODE` have a different P path, so verify build capability. Low-throttle TPA has separate breakpoint, rate, and persistence logic; do not apply the high-throttle expression throughout a flight.[P4], [P5], [P1]

For only the classic high-throttle branch, normalized throttle `t` and breakpoint `b`, the factor can be written as `1 - (tpa_rate/100) * max(t-b,0)/(1-b)`; initialization also constrains the breakpoint. Increasing positive tpa_rate increases attenuation, not high-throttle D damping. Current firmware adds wing-related TPA paths; `PDS` and speed-based TPA are not general 4.5.2 quad capabilities.[P1], [P4], [TPA26]

### 6.4 Throttle Boost and Signal Locations

Version 4.5.2 updates AG, TPA, and dynamic LPF from limited throttle before adding the throttle high-pass component multiplied by `throttle_boost`, with clamping. This is not FF boost or an increase in P/I/D; it changes transient mixer input on throttle rises and falls. `throttle_boost_cutoff` controls the LPF used to form that high-pass component.[M1]

Consequently, `setpoint[3]` includes boost while the throttle used for TPA/AG is pre-boost. **Substituting setpoint[3] into the TPA formula alone does not reconstruct actual TPA.** Also record dynamic idle, airmode, thrust linearization, throttle limiting, RPM limiting, battery state, and motor-output limits as comparison covariates.[M1]

## 7. Inference Prerequisites and Offline DSP Decisions

This section constrains repository methods; it is not an official Betaflight tuning preset.

### 7.1 What Tracking Error and Acceleration Can Establish

Same-axis `setpoint - gyroADC` is the rate error seen by the controller once units, timing, and mode are checked. Report excitation coverage and maneuver/throttle-stratified error, overshoot, and recovery. Small error during quiet flight does not prove good dynamic tracking. Large error can also result from saturation, limited targets, mode transitions, or disturbance; it does not uniquely identify low gains.[P2], [P3]

`accSmooth` is body-frame data. Attitude changes alter the projection of the gravity reference, and an accelerometer offset from the rotation center adds rotation-related components. Without reliable attitude, coordinate conventions, synchronization, gravity handling, and sensor position, body Z cannot be called earth vertical, establish altitude-hold performance, or uniquely diagnose pitch PID. Acceleration alone also cannot reliably determine inclination in dynamic flight.[ACC1], [ACC2]

### 7.2 Separate Direct Steps from Frequency-Domain Deconvolution

Direct rate-step analysis requires identifiable command baselines, amplitudes, directions, dwell, and recovery time. Repeat under similar axis, throttle, voltage, and load conditions without obvious saturation or large cross-axis maneuvers. A finite rise is not an ideal instantaneous step. Analyze stopping/reversal separately from entry. Normalize by the **actual commanded change** if appropriate, report individual events, counts, and dispersion, and do not force normalization by the output tail.

Spectral estimation using `r=setpoint`, `y=gyroADC` gives an **approximate command-to-filtered-angular-rate closed-loop relationship** for that operating condition, including feedforward, feedback, filtering, and limits. It is not the bare airframe plant or a universal response determined only by P/D. H1-type estimates assume local linearity/approximate stationarity, adequate excitation, and noise-correlation conditions; feedback and pilot corrections can violate identification assumptions.[P2], [P3], [D5]

SciPy `csd(r,y)` uses `conj(FFT(r))*FFT(y)`, so a compatible H1 form is `csd(r,y)/welch(r)`. Fix windows, segments, overlap, detrending/mean removal, and physical units. Reversing the conjugation changes phase. Avoid direct division where input power is low; disclose regularization, band selection, and interpolation, and test their sensitivity.[D1], [D3], [D5]

A deconvolved/FRF-derived "estimated step" obtained by IFFT and integration is additionally affected by limited bandwidth, missing DC, windows, causal alignment, boundaries, and regularization. Forcing its tail to 1 can hide gain error or unidentifiable low-frequency behavior. Display normalization requires unnormalized results, scale factor, tail window, DC/steady-state evidence, and sensitivity results alongside it. If low frequencies are unsupported, label steady-state gain unidentifiable; do not recommend PID from normalized overshoot.

Coherence, `abs(Pxy)^2/(Pxx*Pyy)`, describes frequency-dependent association under the chosen estimator. Gate using input power, effective independent averages, confidence/repeatability, and the target band; very few segments can even yield misleadingly high coherence. **There is no universal pass threshold.** Publish any coherence-gating rule, excluded bands, and its effect. Zeroing low-coherence bins before IFFT changes time-domain shape; a smoother curve is not evidence of improvement.[D2], [D3]

### 7.3 Spectral and Time Processing

- Segment at resets, arming intervals, modes, and large gaps before FFT; do not bridge gaps into a continuous record or hide losses with long linear interpolation merely to make an algorithm run.
- Validate each segment's time axis before unifying sample rates. Appropriate downsampling includes anti-alias filtering. `resample_poly` FIR and boundary assumptions are offline choices and cannot reverse pre-recording aliasing.[D4]
- Welch PSD has squared-signal-units/Hz, for example `(deg/s)^2/Hz`. Do not conflate amplitude spectra, power spectra, and PSD. Match bands, window durations, scaling, and color limits; generic digital-signal PSD is not dBm/Hz without a justified reference.[D1]
- Separate commanded maneuvers, impacts/landings, propwash, and relatively steady noise segments, then stratify by RPM/throttle. D spectra also depend on differentiation, gains, dynamic D, and TPA; total RMS alone cannot establish sufficient filtering.[P2]
- Explicitly labeled zero-phase forward/backward filtering can serve offline display/analysis. Its phase behavior is not the delay of the FC's real-time causal filter and does not establish "zero-delay" flight filtering.[D6]

## 8. Three Actual Flight Checks and Multiple Logs

**Three actual flights are the project's default workflow, not an official guarantee or three software-analysis runs.** Separate PID-only and filter-only rounds are not mandatory. Review both in every round, explicitly justifying unchanged settings too.

| Flight check | Inputs and maneuvers | Required deliverable |
| --- | --- | --- |
| First: baseline | After mechanical, telemetry, and log-quality checks, use an existing configuration confirmed safe to fly; record repeatable rate maneuvers, throttle changes, and intended-use segments | Complete baseline diagnosis and a **combined PID+filter proposal**: mark each axis's P/I/D/dynamic D/FF, AG, TPA, throttle boost, gyro/D-term/RPM/dynamic-notch settings as change or retain, with evidence, risk, and validation points. Retain unsupported settings rather than inventing numbers. |
| Second: comparison and revision | Verify the complete applied change set, repeat reasonably matched maneuvers, directions, and operating conditions, and record battery, wind, load, and temperature | Compare baseline and new logs by comparable segments; identify improvement, regression, and non-comparability, then deliver combined PID+filter revisions and retained settings. Multiple simultaneous changes permit package-level evaluation, not invented single-parameter causality. |
| Third: validation and remaining issues | Use the second revision, repeat validation maneuvers, cover intended use, and retain independent events for validation | Mark each target as pass / fail / not covered. List remaining noise, tracking, telemetry, thermal, saturation, or identification issues and conditional next steps. One attractive curve does not establish global optimality. |

A suitably equipped operator conducts the flights. Stop first for unresolved mechanical faults, abnormal motor heat/noise, telemetry faults, clear instability, or unsafe surroundings. Three flights are not a quota requiring unsafe flying. If data are inadequate or the third flight fails, report missing evidence rather than guaranteeing convergence. Joint PID/filter changes make complete-package validation practical but reduce individual-parameter causal separation; disclose that tradeoff.

### Multiple-Log Engineering Process

1. Build a manifest: file hash, original path, flight number, log index, time, firmware/board/build, configuration snapshot, actual change set, and decoder/analyzer versions. One BBL may contain multiple arming sessions; file count is not flight count.[U2]
2. Decode each log separately and check fields/units, time quality, actual telemetry, and usable bandwidth. Group differing firmware, craft, props, and sensor paths before comparison; do not merge blindly.
3. Label each continuous segment with mode, maneuver, axis, direction, angular-rate amplitude, throttle/RPM, voltage, and saturation indicators; retain exclusions and reasons.
4. Present per-log/per-event results before matched-condition aggregates. Standardize spectral settings and disclose duration, event count, and coverage. Long hover logs must not swamp short critical maneuvers, and deconvolution must not cross log boundaries.
5. Separate tuning events from third-flight validation events. Overlapping windows are not independent flight samples; avoid spurious statistical precision with few flights.
6. Report observations, candidate explanations, combined changes, validation, and unknowns. Unmatched before/after flights can be exploratory evidence, not causal improvement percentages. Even three apparently better flights do not eliminate wind, voltage, pilot, or order effects.

## 9. Practical Data Intake Checklist

- Complete original BBL/BFL/TXT files with log indices/arming intervals, not screenshots, truncated CSVs, or selected best segments only.
- `version`, `status`, `tasks`, complete `dump all`/appropriate configuration export, active PID/rate profile, build features, and Configurator/App version. These are requested read-only evidence, not FC commands executed in this research.
- Actual before/after configurations and change sets for every flight: PID/dynamic D, FF/RC smoothing, AG, TPA including low-throttle settings, throttle boost/limit, gyro/D-term LPFs, RPM/dynamic notch, idle, airmode, mixer, thrust linearization, and output limits.
- FC/gyro model and orientation, gyro/PID/log rates, field selections, high-resolution mode, debug mode/axis, `motorOutput`, `acc_1G`, export units, and missing-frame statistics.
- Motor model/KV/verified magnetic pole count, ESC model/firmware/PWM settings, bidirectional-protocol support, per-motor telemetry, and packet errors. Configuration screenshots do not replace telemetry.
- Frame, prop size/model/condition, craft and battery mass, payload/center of gravity, mounting, screws/bearings/motors/arms, and recent crash/repair history.
- RX protocol, actual packet rate, rate curves, RC smoothing, and link anomalies. FF interpretation must be downgraded if these are missing.
- Battery specification/state, voltage range, wind, pilot, maneuver order/markers, mode, positive/negative same-axis maneuvers, throttle changes, and intended-use segments for each flight.
- Safety checks, motor-temperature measurement method/timing, abnormal sound, desync, saturation, and pilot observations. Uncalibrated touch is not a precise temperature measurement.
- Earth-frame linear acceleration or altitude claims additionally require attitude/coordinate definitions, sensor location, synchronization, and gravity-handling evidence; accSmooth alone is insufficient.

## 10. Tool Sufficiency and PTstepcalc Boundaries

### Verified Local Facts

The supplied PIDtoolbox installation contains `PIDtoolbox.exe` and `blackbox_decode.exe`. Only the latter's `--help` was run during this research. It reports **v0.4.6, Jun 10 2021 22:06:07**, with SHA256 `D7379ED4EC0ABBB77A3461C9DD4A93AF440F243E0879CF197BF60739278565A0`. This proves the help entry point runs, not correct support for 4.5.2 high resolution, all fields, or 2026.6.2. This research did not decode a user flight log or run the PIDtoolbox GUI; subsequent local project regressions are recorded separately from source verification.

Official `blackbox-tools` provides unit options, log indices, missing-frame statistics, and CSV decoding. Official Blackbox Explorer source includes high-resolution and mechanical-RPM display conversions as an independent field cross-check. Referenced source snapshots are `d89f96b983d0f5c8f053acf003ee2998b02b5b0f` and `e179902df4e38f24d4b61f114bf856a196c995be` respectively; these do not establish the provenance of the local executable.[U1], [U2], [E1]

### Capability Sufficiency

| Task | Minimum capability and finding |
| --- | --- |
| Traceable decoding and unit validation | Version-appropriate decoder, complete headers, error statistics, and golden-log/independent-viewer cross-checks. The existing exe's presence is not a compatibility pass. |
| Noise and tracking diagnosis | Reliable decoding, time/unit checks, mature array/DSP libraries, and segmented/multiple-log reports can support offline analysis in principle; PIDtoolbox GUI automation is not required.[D1], [D2], [D3] |
| A new step/FRF analyzer | Also requires tests for known transfer relationships, pure delay, weak excitation, missing frames, saturation, dynamic gains, and cross-axis interference. Similar graphics are not acceptance. |
| Safe settings and actual improvement | Also requires complete craft/configuration/telemetry, thermal evidence, and three actual operator-conducted flight checks. Offline tools cannot guarantee safety or automatically confirm improvement. |
| PIDtoolbox numerical equivalence | Insufficient evidence; do not claim equivalence, a replacement implementation, or reproduction of its current algorithm. |

### Original PTstepcalc Availability

The author's repository page, GitHub API, and raw `master/PTstepcalc.m` were attempted; all returned 404 in this research. The author's website was reachable, but no source suitable for checking this algorithm was obtained. This does not prove source never existed or that the author stopped maintenance.[PT1], [PT2], [PT3]

Accordingly, the **original PTstepcalc implementation was not reviewed, ported, or copied**. Third-party forks/ports were not substituted for the author's first-party algorithm or current PIDtoolbox. Windowing, deconvolution regularization, coherence gating, tail normalization, statistical selection, and version differences remain unknown. Algorithmic/numerical comparison requires specified-version source that can be inspected under its authorization terms and reference outputs in a later task.

## 11. Version Unknowns and Release Acceptance

- The listed paths were checked for 4.5.2 and 2026.6.2, not every intermediate release, board, cloud build, ESC, or sensor. Custom builds require their actual version/configuration and matching source.
- Official 2026.6 notes describe BIQUAD-to-SVF implementation/option changes and a re-derived thrust-linearization curve. These are upgrade cautions, not evidence that identical values transfer across releases. Rolling release notes can include later material outside the selected tag; check tagged source for exact differences.[W26]
- The Wiki conflicts with tagged source in CLI names and debug layouts. An official site's current page is not a complete 4.5.2 specification. Feed Forward 2.0 has historical context, and original PIDtoolbox methods remain inaccessible.[WD], [WFF]
- Before releasing the new repository, fixed fixtures should verify: no double scaling in normal/high-resolution logs, mechanical RPM/pole conversion, missing fields not fabricated as zero observations, rejection of blind mixed-version aggregation, missing-frame/time-wrap handling, known-delay phase direction, rejection or uncertainty for weak excitation and non-unit DC/tails, and the same conclusions in both languages.
- Three-flight reports must cover PID and filters in proposal/comparison/validation and distinguish checks not performed, conditions not covered, and non-identifiable individual-parameter causality. The third flight is not an automatic pass.

## 12. Primary Source Index

Code links pin complete commits and relevant lines. Official online guides are retrieval-date snapshots and can change. DSP documentation is pinned to SciPy 1.16.2 for algorithm definitions, not as a required project dependency version. PT links document availability checks, not algorithm contents.

- Versions: [V45], [T45], [V26], [T26].
- 4.5.2 logging/sampling and current fields: [B1], [B2], [B3], [B4], [B5], [B6], [B7], [B26], [B26F].
- Gyro/RPM/acceleration: [G1], [G2], [G3], [G26], [R1], [R2], [R3], [R26], [ARM45], [ACC1], [ACC2].
- PID/sliders/CLI/throttle: [P1], [P2], [P3], [P4], [P5], [S45], [C45], [N45], [M1], [A1], [A2], [A3], [A26], [F1], [F2].
- D debug and current implementation differences: [DL45], [DLS45], [P26], [I26], [N26], [S26], [F26], [TPA26].
- Official guides and tools: [W45], [W26], [WD], [WFF], [WPID], [WDEBUG], [WRPM], [U1], [U2], [E1].
- DSP/method boundaries: [D1], [D2], [D3], [D4], [D5], [D6]; author entry points: [PT1], [PT2], [PT3].

[V45]: https://github.com/betaflight/betaflight/releases/tag/4.5.2
[T45]: https://api.github.com/repos/betaflight/betaflight/git/ref/tags/4.5.2
[V26]: https://github.com/betaflight/betaflight/releases/tag/2026.6.2
[T26]: https://api.github.com/repos/betaflight/betaflight/git/ref/tags/2026.6.2
[B1]: https://github.com/betaflight/betaflight/blob/024f8e13d4e642eb6a380308685b9ea3aa3ef1a2/src/main/blackbox/blackbox.c#L182-L269
[B2]: https://github.com/betaflight/betaflight/blob/024f8e13d4e642eb6a380308685b9ea3aa3ef1a2/src/main/blackbox/blackbox.c#L1126-L1175
[B3]: https://github.com/betaflight/betaflight/blob/024f8e13d4e642eb6a380308685b9ea3aa3ef1a2/src/main/blackbox/blackbox.c#L460-L536
[B4]: https://github.com/betaflight/betaflight/blob/024f8e13d4e642eb6a380308685b9ea3aa3ef1a2/src/main/blackbox/blackbox.c#L1361-L1402
[B5]: https://github.com/betaflight/betaflight/blob/024f8e13d4e642eb6a380308685b9ea3aa3ef1a2/src/main/blackbox/blackbox.c#L322-L343
[B6]: https://github.com/betaflight/betaflight/blob/024f8e13d4e642eb6a380308685b9ea3aa3ef1a2/src/main/blackbox/blackbox.c#L2075-L2096
[B7]: https://github.com/betaflight/betaflight/blob/024f8e13d4e642eb6a380308685b9ea3aa3ef1a2/src/main/blackbox/blackbox.c#L1749-L1756
[B26]: https://github.com/betaflight/betaflight/blob/e0b7bb01b17b21351057e9ead2d1ab39dd44fa16/src/main/blackbox/blackbox.c#L1254-L1306
[B26F]: https://github.com/betaflight/betaflight/blob/e0b7bb01b17b21351057e9ead2d1ab39dd44fa16/src/main/blackbox/blackbox.c#L199-L300
[G1]: https://github.com/betaflight/betaflight/blob/024f8e13d4e642eb6a380308685b9ea3aa3ef1a2/src/main/sensors/gyro.c#L389-L455
[G2]: https://github.com/betaflight/betaflight/blob/024f8e13d4e642eb6a380308685b9ea3aa3ef1a2/src/main/sensors/gyro_init.c#L246-L268
[G3]: https://github.com/betaflight/betaflight/blob/024f8e13d4e642eb6a380308685b9ea3aa3ef1a2/src/main/sensors/gyro_filter_impl.c#L22-L90
[G26]: https://github.com/betaflight/betaflight/blob/e0b7bb01b17b21351057e9ead2d1ab39dd44fa16/src/main/sensors/gyro.c#L449-L459
[R1]: https://github.com/betaflight/betaflight/blob/024f8e13d4e642eb6a380308685b9ea3aa3ef1a2/src/main/flight/rpm_filter.c#L71-L190
[R2]: https://github.com/betaflight/betaflight/blob/024f8e13d4e642eb6a380308685b9ea3aa3ef1a2/src/main/drivers/dshot.c#L148-L160
[R3]: https://github.com/betaflight/betaflight/blob/024f8e13d4e642eb6a380308685b9ea3aa3ef1a2/src/main/drivers/dshot.c#L292-L343
[R26]: https://github.com/betaflight/betaflight/blob/e0b7bb01b17b21351057e9ead2d1ab39dd44fa16/src/main/drivers/dshot.c#L184-L191
[ARM45]: https://github.com/betaflight/betaflight/blob/024f8e13d4e642eb6a380308685b9ea3aa3ef1a2/src/main/fc/core.c#L364-L370
[ACC1]: https://github.com/betaflight/betaflight/blob/024f8e13d4e642eb6a380308685b9ea3aa3ef1a2/src/main/sensors/acceleration.c#L44-L84
[ACC2]: https://www.analog.com/en/resources/app-notes/an-1057.html
[P1]: https://github.com/betaflight/betaflight/blob/024f8e13d4e642eb6a380308685b9ea3aa3ef1a2/src/main/flight/pid_init.c#L396-L434
[P2]: https://github.com/betaflight/betaflight/blob/024f8e13d4e642eb6a380308685b9ea3aa3ef1a2/src/main/flight/pid.c#L1017-L1081
[P3]: https://github.com/betaflight/betaflight/blob/024f8e13d4e642eb6a380308685b9ea3aa3ef1a2/src/main/flight/pid.c#L944-L993
[P4]: https://github.com/betaflight/betaflight/blob/024f8e13d4e642eb6a380308685b9ea3aa3ef1a2/src/main/flight/pid.c#L280-L295
[P5]: https://github.com/betaflight/betaflight/blob/024f8e13d4e642eb6a380308685b9ea3aa3ef1a2/src/main/flight/pid.c#L796-L800
[DL45]: https://github.com/betaflight/betaflight/blob/024f8e13d4e642eb6a380308685b9ea3aa3ef1a2/src/main/flight/pid.c#L864-L878
[DLS45]: https://github.com/betaflight/betaflight/blob/024f8e13d4e642eb6a380308685b9ea3aa3ef1a2/src/main/flight/pid.c#L248-L250
[S45]: https://github.com/betaflight/betaflight/blob/024f8e13d4e642eb6a380308685b9ea3aa3ef1a2/src/main/config/simplified_tuning.c#L31-L114
[C45]: https://github.com/betaflight/betaflight/blob/024f8e13d4e642eb6a380308685b9ea3aa3ef1a2/src/main/cli/settings.c#L1190-L1254
[N45]: https://github.com/betaflight/betaflight/blob/024f8e13d4e642eb6a380308685b9ea3aa3ef1a2/src/main/fc/parameter_names.h#L79-L130
[M1]: https://github.com/betaflight/betaflight/blob/024f8e13d4e642eb6a380308685b9ea3aa3ef1a2/src/main/flight/mixer.c#L643-L677
[A1]: https://github.com/betaflight/betaflight/blob/024f8e13d4e642eb6a380308685b9ea3aa3ef1a2/src/main/flight/pid.c#L298-L316
[A2]: https://github.com/betaflight/betaflight/blob/024f8e13d4e642eb6a380308685b9ea3aa3ef1a2/src/main/flight/pid.c#L845-L855
[A3]: https://github.com/betaflight/betaflight/blob/024f8e13d4e642eb6a380308685b9ea3aa3ef1a2/src/main/flight/pid.c#L1114-L1123
[A26]: https://github.com/betaflight/betaflight/blob/e0b7bb01b17b21351057e9ead2d1ab39dd44fa16/src/main/flight/pid.c#L465-L483
[F1]: https://github.com/betaflight/betaflight/blob/024f8e13d4e642eb6a380308685b9ea3aa3ef1a2/src/main/fc/rc.c#L499-L624
[F2]: https://github.com/betaflight/betaflight/blob/024f8e13d4e642eb6a380308685b9ea3aa3ef1a2/src/main/fc/rc.c#L468-L480
[P26]: https://github.com/betaflight/betaflight/blob/e0b7bb01b17b21351057e9ead2d1ab39dd44fa16/src/main/flight/pid.c#L1347-L1375
[I26]: https://github.com/betaflight/betaflight/blob/e0b7bb01b17b21351057e9ead2d1ab39dd44fa16/src/main/flight/pid_init.c#L495-L507
[N26]: https://github.com/betaflight/betaflight/blob/e0b7bb01b17b21351057e9ead2d1ab39dd44fa16/src/main/fc/parameter_names.h#L121-L156
[S26]: https://github.com/betaflight/betaflight/blob/e0b7bb01b17b21351057e9ead2d1ab39dd44fa16/src/main/config/simplified_tuning.c#L31-L60
[F26]: https://github.com/betaflight/betaflight/blob/e0b7bb01b17b21351057e9ead2d1ab39dd44fa16/src/main/fc/rc.c#L496-L535
[TPA26]: https://github.com/betaflight/betaflight/blob/e0b7bb01b17b21351057e9ead2d1ab39dd44fa16/src/main/flight/pid.c#L264-L272
[W45]: https://betaflight.com/docs/wiki/release/Betaflight-4-5-Release-Notes#17-blackbox-and-logging-updates
[W26]: https://betaflight.com/docs/wiki/release/Betaflight-2026-6-Release-Notes
[WD]: https://betaflight.com/docs/wiki/guides/current/Dynamic-D
[WFF]: https://betaflight.com/docs/wiki/guides/current/Feed-Forward-2-0
[WPID]: https://betaflight.com/docs/wiki/app/pid-tuning-tab
[WDEBUG]: https://betaflight.com/docs/wiki/guides/current/Debug-Modes#cli-information-commands
[WRPM]: https://betaflight.com/docs/wiki/guides/current/DSHOT-RPM-Filtering
[U1]: https://github.com/betaflight/blackbox-tools/blob/d89f96b983d0f5c8f053acf003ee2998b02b5b0f/src/blackbox_decode.c#L190-L215
[U2]: https://github.com/betaflight/blackbox-tools/blob/d89f96b983d0f5c8f053acf003ee2998b02b5b0f/Readme.md#L16-L60
[E1]: https://github.com/betaflight/blackbox-log-viewer/blob/e179902df4e38f24d4b61f114bf856a196c995be/src/flightlog_fields_presenter.js#L1633-L1697
[D1]: https://docs.scipy.org/doc/scipy-1.16.2/reference/generated/scipy.signal.welch.html
[D2]: https://docs.scipy.org/doc/scipy-1.16.2/reference/generated/scipy.signal.coherence.html
[D3]: https://docs.scipy.org/doc/scipy-1.16.2/reference/generated/scipy.signal.csd.html
[D4]: https://docs.scipy.org/doc/scipy-1.16.2/reference/generated/scipy.signal.resample_poly.html
[D5]: https://www.mathworks.com/help/signal/ref/tfestimate.html
[D6]: https://docs.scipy.org/doc/scipy-1.16.2/reference/generated/scipy.signal.sosfiltfilt.html
[PT1]: https://github.com/bw1129/PIDtoolbox
[PT2]: https://raw.githubusercontent.com/bw1129/PIDtoolbox/master/PTstepcalc.m
[PT3]: https://pidtoolbox.com/
