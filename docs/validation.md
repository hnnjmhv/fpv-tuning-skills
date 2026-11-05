# Release Validation / 发布验证

## Exercised / 已执行

- Deterministic synthetic tests cover contiguous FFT windows, tone RMS recovery, units, missing fields, Nyquist limits, header-based motor output bounds, RPM enable-vs-telemetry distinctions, and diagnostic-only response output.
- Three distinct generated logs exercise baseline, recheck, final review, baseline comparison, duplicate-content refusal and an unevaluated acceptance checklist.
- Plan tests cover matching profiles/firmware/configuration, existing evidence paths, supported ranges, enum mapping, simultaneous PID/filter proposals, simplified-controller consistency, full/differential output, explicit save and rollback.
- Both language skills pass the repository validator. The English skill also passes the standard skill-creator validator. Chinese naming is an intentional local convention with an English-compatible alternative.
- Install, backed-up update and wheel build have been exercised in an isolated environment. A legacy local log was decoded and analyzed without publication; approximately 205 seconds at 1 kHz produced 186 contiguous flight windows. This was a Betaflight 4.5.1 analysis-only regression, not a 4.5.2 plan or flight acceptance.

## Independent Forward Test / 独立演练

An evaluator used the skills and generated artifacts under an ignored local directory. Six material cases were reproduced: literal OFF flags, firmware-invalid bounds, manual/simplified bypasses, setpoint units, dynamic-D control identification, and analyzed-profile identity. These cases were corrected with dedicated regression tests before release.

Synthetic tests establish software behavior. They do not establish the best PID values, thermal performance or flight safety for a real airframe.

## Not Claimed / 未宣称完成

- No flight controller was written, no real three-flight tuning experiment was flown for this release, and no real-airframe tune is certified.
- High-resolution logs do not yet have a validated scaling reference; executable plans and quantitative comparison are blocked for them.
- CLI compilation is limited to the supported Betaflight 4.5.2 subset; 2026 firmware has documented differences but no executable plan adapter.
- No numerical equivalence with PIDtoolbox or blanket compatibility of the old decoder is claimed.
- Public CI tests synthetic data on Windows/Linux and Python 3.10/3.13. CI status is visible on the repository Actions page.

The initial Windows 3.10 CI build exposed a locale-dependent editable-install error caused by a non-ASCII package source path. The engine was moved to the conventional ASCII `src/fpv_tune` layout while preserving both skill names. Installed Chinese skills receive a runtime copy from that canonical source, and command output uses UTF-8.
