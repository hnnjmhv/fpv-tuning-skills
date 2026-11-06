# Command-Line Usage

Run `fpv-tune` in the Python environment where the project dependencies are installed.

## Analyze a Blackbox Log

```sh
fpv-tune inspect --log flight-1.bbl
fpv-tune start --session outputs/my-build --checks 3
fpv-tune analyze --log flight-1.bbl --decoder /path/to/blackbox_decode --session outputs/my-build --plots
```

`inspect` lists the flight sections. The largest by byte size is selected by default; use `--index N` to choose one. Exclude takeoff, landing or impacts with `--start-s` and `--end-s`, measured from the start of the selected log section.

For flights two and three, run `analyze` on the same session with each new log. Use `--metadata context.json` for the build, props, battery and flight mode, and `--symptom` for the current problem.

For a single analysis, replace `--session` with `--out outputs/check`.

## Analyze CSV

```sh
fpv-tune analyze --csv flight.csv --config dump.txt --profile 0 --out outputs/check --plots
```

Label time with `(us)`, `(ms)` or `(s)`, or provide `--time-unit`. Label gyro and setpoint with `(deg/s)`; `(rad/s)` is converted. Unlabelled setpoints are inferred only for confirmed non-high-resolution Betaflight 4.5 logs.

Select multi-profile configurations with `--profile`. CLI profiles start at zero.

## Generate Settings

The skill fills in `changes.json` from the analysis. Each entry includes the parameter, proposed value, reason and paths to the supporting measurements:

```json
{
  "changes": [
    {
      "key": "p_pitch",
      "value": 42,
      "reason": "Format example; replace with the reason from this analysis.",
      "evidence": ["axes.pitch.tracking.normalized_mae"]
    }
  ]
}
```

The example value 42 is not a tuning recommendation.

```sh
fpv-tune plan --analysis outputs/my-build/check-1/analysis.json --config dump.txt --profile 0 --changes changes.json --out outputs/my-plan
```

Output files:

- `candidate-cli.txt`: changed settings.
- `full-reviewed-cli.txt`: all known supported settings.
- `rollback-cli.txt`: the previous settings.
- `plan.json`: reasons and measurement references.

Add `--include-save` to include `save` at the end. Unrecorded or unsupported settings are listed in the report rather than filled with defaults. Manual PID or low-pass changes disable their corresponding simplified controls to prevent slider recalculation from overwriting the values.

## Results

Each check directory contains `analysis.json`, reports, a parameter table and optional spectrum plots. The second check compares with the first; the third also compares with the original baseline and creates `validation.json` for actual flight results.

Reprocessing one log does not count as a new flight. Start a follow-up session if further tuning is needed.
