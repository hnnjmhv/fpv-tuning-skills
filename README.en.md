# FPV Tuning Skills

[中文](README.md)

Chinese and English Codex skills for blackbox-based PID and filter review, powered by one offline Python engine. The default workflow uses **three actual flight checks**.

The tool measures log timing, contiguous-window spectra, low-command spectra, throttle coverage, rate-tracking error, RPM field coverage, motor output limits and throttle events. It compares matched throttle/command strata and compiles reviewed proposals into full, differential and rollback CLI files.

It cannot establish an optimal tune from an arbitrary log, interpret body-Z acceleration as earth-frame vertical movement, replace motor-temperature/mechanical checks, or write to a flight controller. Its response diagnostics are not the PIDtoolbox step-response algorithm.

## Three Flight Checks

| Check | Input | Output | Next step |
| --- | --- | --- | --- |
| 1: Baseline | Original log, current dump/diff, build and symptoms | Full review, PID + filter proposal, rollback | Fly the selected candidate |
| 2: Recheck | Second flight log and actual applied settings | Matched comparison and revisions | Fly the revision |
| 3: Evaluation | Third flight log, temperatures and pilot feedback | Evidence of improvement, unresolved issues, retain/revert decision | Test further if needed |

Every check covers PID and filters together. Combined proposals are supported. Three checks are the default, not a requirement to separate PID and filters or a promise of convergence. Configure another count with `--checks`.

## Install

Python 3.10+ is required. The shared engine lives in `src/fpv_tune`; the installer copies that same source into the Chinese skill's runtime entrypoint. Raw logs also require a user-supplied firmware-compatible `blackbox_decode`. No upstream executables are redistributed.

```sh
python -m venv .venv
# Windows:
.venv/Scripts/python -m pip install ".[dev,plots]"
.venv/Scripts/python tools/install_skills.py
# Linux/macOS: replace .venv/Scripts/python with .venv/bin/python.
```

Activate the virtual environment before invoking `fpv-tune`, or use its explicit executable path. The installer targets `$CODEX_HOME/skills`, or `~/.codex/skills` when unset. Use `--update` to replace existing skills with an external backup. Invoke `$穿越机调参` or `$fpv-drone-tuning`; use the language requested by the user. Clients requiring strict ASCII hyphen-case names can use the English entrypoint; the repository validator intentionally supports the existing Chinese name.

The ordinary wheel installation above also works from non-ASCII checkout paths. For development, use an ASCII checkout path with `pip install -e ".[dev,plots]"`.

## Run

```sh
fpv-tune inspect --log flight-1.bbl
fpv-tune start --session outputs/my-build --checks 3
fpv-tune analyze --log flight-1.bbl --decoder /path/to/blackbox_decode --session outputs/my-build --metadata flight-context.json --plots
```

The largest section by bytes is the default selection, not necessarily the longest or best flight. Choose `--index N` explicitly if needed. Trim ground impacts with `--start-s/--end-s`.

For decoded CSV, the time column needs `(us)`, `(ms)` or `(s)`, or `--time-unit`. Gyro and setpoint should be labelled `(deg/s)`; labelled `(rad/s)` is converted to deg/s. Unlabelled setpoint rates are inferred only for the confirmed non-high-resolution Betaflight 4.5 format. Supply `--config dump.txt --profile 0` for the actual configuration. CLI profiles are zero-based: GUI Profile 1 is `profile 0`.

Each check emits `analysis.json`, both language reports, parameter coverage and optional plots. Repeating `analyze` with the session advances the journal and compares to the previous flight. Identical content cannot count as a new check.

The third check also emits `baseline-comparison.json` against the first log and an unevaluated `validation.json` with criteria to mark pass, fail or not covered. Reaching three never implies automatic acceptance.

## Reviewed Plans

Create a `changes.json` object with a `changes` list. Each entry has a validated `key`, proposed `value`, a `reason`, and an `evidence` list of paths in `analysis.json`, such as `axes.pitch.tracking.normalized_mae`. Evidence paths establish traceability, not proof that a particular gain change is correct.

```sh
fpv-tune plan --analysis outputs/my-build/check-1/analysis.json --config dump.txt --profile 0 --changes changes.json --out outputs/my-plan
```

The output includes `candidate-cli.txt`, `full-reviewed-cli.txt`, `rollback-cli.txt`, `plan.json` and both language explanations. Add `--include-save` only when a save command is wanted. Missing values are marked `needs_data`, never substituted with defaults.

Executable plans currently support a conservative parameter subset of **Betaflight 4.5.2**. Other firmware versions are analysis-only. Manual PID/filter changes explicitly disable their corresponding simplified controls to avoid recalculation conflicts. Motor protocols, receiver setup, failsafe and GPS are out of scope.

## Evidence and Validation

Read [the implementation assessment](docs/assessment.en.md), [primary-source research](docs/research.en.md), [the three-check workflow](docs/workflow.en.md), and [measurement methodology](docs/methodology.en.md).

PIDtoolbox, Blackbox Explorer and Betaflight App/CLI serve complementary purposes; motor temperatures, DShot errors and mechanical condition remain relevant. [Official RPM filtering guidance](https://betaflight.com/docs/wiki/guides/current/DSHOT-RPM-Filtering)

```sh
python -m pytest
python tools/validate_skills.py
python examples/generate_demo.py --out .local/demo
fpv-tune analyze --csv .local/demo/flight-1.csv --config .local/demo/dump.txt --profile 0 --out .local/demo/report --plots
```

Tests exercise discontinuous data, units, duplicate logs, scoped profiles, enum conversions, simplified controls, parameter ranges and rollback behavior. Demo data is generated synthetically. MIT applies to original project code; upstream firmware, PIDtoolbox code, executables and private logs are not bundled.
