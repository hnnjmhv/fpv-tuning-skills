# Measurement Contract / 测量约定

## Timing and windows / 时间轴与窗口

Time units must be explicit. Positive normal intervals estimate logging rate. Duplicate/backward timestamps block planning; gaps split windows. Interval jitter above 5% and fewer than five accepted windows block plan compilation. These are implementation quality gates, not Betaflight tuning or flight-safety thresholds.

时间单位必须明确；超过标称间隔 1.5 倍、小于 0.5 倍或时间倒退会断段。频谱只用完整连续窗。默认窗长 1 秒，可设 0.5–4 秒。分析会保留采样率、有效窗数量和缺口记录。

The throttle selection `rcCommand[3] > 1050` reduces ground data but does not prove flight or arming. Low-setpoint means all three recorded commands remain below 50 deg/s and throttle is between 1100 and 1750 over a full window. It does not establish a steady hover. Trim impacts and inspect modes separately.

油门筛选不是解锁检测，低杆量窗口也不等于稳态悬停。模式变化、急停、撞击、尾流等需要结合动作进行解释。

## Spectra / 频谱

Use SciPy Welch PSD with a Hann window and constant detrend within each contiguous window. Average densities, then sum bin power within complete bands 20–80, 80–180, 180–450, 450–900 Hz. A band extending beyond log Nyquist is unavailable, not zero. Sampling does not remove acquisition aliasing.

PSD units are signal-unit squared per Hz. Gyro post requires explicit deg/s labels. Unlabelled pre-gyro remains raw logged units; no undocumented pre/post attenuation ratio is computed. D-term is firmware control output, dependent on gains/TPA, and is plotted on its own panel.

[SciPy Welch documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.welch.html)

## Tracking and response / 跟随与响应

The tool measures aligned rate error for command magnitude at least 80 deg/s with at least 200 active samples. These are reporting selections, not universal good/bad thresholds. Coherence is diagnostic only. No deconvolved tail is forced to 1, and no inferred overshoot automatically produces a D recommendation.

缺少 setpoint 或正确 gyro 单位就不能作可靠的跟随判断。高分辨率日志标度尚未建立黄金参考验证时，阻止可执行方案与定量复飞比较。

## Comparison / 复飞比较

Compare medians within common throttle bins (200 command units wide) and command-RMS bins (<40, 40–150, >=150 deg/s). Require at least three windows per flight per common stratum. This controls only a limited subset of confounds and does not establish causality or a confidence interval across independent flights.

Logs with different known firmware, board, props, battery cell count or mode are rejected for direct comparison; absent context is reported. D-term comparisons describe observed control output, not filter attenuation independent of gains.

## Configuration plans / 参数方案

The 4.5.2 parameter vocabulary is a conservative subset of valid settings, not the entire firmware CLI schema. It validates supported keys, types, lookup enums, project ranges and cross-parameter bounds; it does not prove a tuning decision. Proposed values require a human/agent rationale plus existing non-null analysis paths. Matching log/current config and an explicit CLI profile are required.

`full-reviewed-cli.txt` covers recorded supported values only. `needs_data` items are omitted, never defaulted. Manual values disable the corresponding simplified controller, while rollback restores both the prior mode and values. No flight-controller write transport is included.

The proposal status remains `candidate_not_flight_validated`. The third journal entry remains `checks_analyzed_review_required`. Only actual flight evidence and operator assessment can support a tuned conclusion.
