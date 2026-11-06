# FPV Auto Tuning Skill

[中文](README.md)

## Install

Download the project and run these commands from its directory:

```sh
python -m pip install ".[plots]"
python tools/install_skills.py
```

If the dependencies are already installed, update the skills with:

```sh
python tools/install_skills.py --update
```

Requires Python 3.10 or newer.

## Use

Invoke `$fpv-drone-tuning` in Codex, attach the blackbox log and current configuration, and describe the build and the problem. For example:

```text
Use $fpv-drone-tuning to adjust PID and filters together from this log.
The quad shakes slightly on throttle punches and feels loose.
```

Tune across three flights:

1. Send the first flight log to get the initial settings.
2. Apply the settings, fly again, and send the new log for revisions.
3. Fly once more to check shaking, tracking and motor temperature, then decide which settings to keep or revert.

Each pass checks PID, D-min, FF, both low-pass stages, RPM filtering, notches and throttle settings. It provides the full settings, changed commands and rollback commands. Continue with another flight if needed.

## Files and Versions

- Logs: `.bbl`, `.bfl` or decoded CSV.
- Configuration: a Betaflight `dump` or `diff all` export.
- Raw logs require `blackbox_decode`, available in a PIDtoolbox installation.
- Configuration commands are currently checked against Betaflight 4.5.2. Other firmware needs a compatibility review after analysis.
- CLI `profile 0` corresponds to GUI PID Profile 1.

Apply settings through Betaflight CLI. Original flight logs stay local.

[Command-line usage](docs/usage.en.md) · [Flight workflow](docs/workflow.en.md) · [References](docs/research.en.md) · [Downloads](https://github.com/hnnjmhv/fpv-tuning-skills/releases)
