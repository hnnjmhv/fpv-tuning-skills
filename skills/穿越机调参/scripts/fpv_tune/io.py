"""Read blackbox data without treating firmware headers as executable commands."""

from __future__ import annotations

import hashlib
import math
import re
import subprocess
from pathlib import Path

import pandas as pd


class InputError(ValueError):
    pass


SIGNATURE = b"H Product:Blackbox flight data recorder"


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def list_logs(path: Path) -> list[dict]:
    data = path.read_bytes()
    offsets = [match.start() for match in re.finditer(re.escape(SIGNATURE), data)]
    if not offsets:
        raise InputError("No blackbox header found; provide the original .bbl/.bfl file.")
    logs = []
    for pos, start in enumerate(offsets):
        end = offsets[pos + 1] if pos + 1 < len(offsets) else len(data)
        headers = {}
        # Headers are consecutive text lines; the rest of the block is binary data.
        for line in data[start:min(end, start + 131072)].splitlines():
            if not line.startswith(b"H "):
                break
            key, separator, value = line[2:].partition(b":")
            if separator:
                headers[key.decode("latin-1").strip()] = value.decode("latin-1").strip()
        logs.append({"index": pos + 1, "offset": start, "size_bytes": end - start,
                     "sha256": hashlib.sha256(data[start:end]).hexdigest(), "headers": headers})
    return logs


def select_log(logs: list[dict], index: int | None) -> dict:
    if index is None:
        return max(logs, key=lambda item: item["size_bytes"])
    selected = next((item for item in logs if item["index"] == index), None)
    if selected is None:
        raise InputError(f"Log index {index} does not exist; available: {[x['index'] for x in logs]}")
    return selected


def decode(path: Path, decoder: Path, index: int, destination: Path) -> dict:
    if not decoder.is_file():
        raise InputError("Decoder not found; pass --decoder /path/to/blackbox_decode.")
    command = [str(decoder.resolve()), "--stdout", "--index", str(index),
               "--unit-rotation", "deg/s", str(path.resolve())]
    try:
        with destination.open("wb") as stream:
            process = subprocess.run(command, stdout=stream, stderr=subprocess.PIPE, timeout=180, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise InputError(f"Decoder failed: {type(error).__name__}") from error
    diagnostic = process.stderr.decode("utf-8", errors="replace")
    destination.with_suffix(".stderr.txt").write_text(diagnostic, encoding="utf-8")
    if process.returncode:
        raise InputError(f"Decoder exited {process.returncode}; see the local .stderr.txt file.")
    match = re.search(r"(\d+) frames failed to decode", diagnostic)
    version = subprocess.run([str(decoder.resolve()), "--help"], capture_output=True, timeout=10)
    first_line = (version.stdout + version.stderr).decode("utf-8", errors="replace").splitlines()
    return {"failed_frames": int(match.group(1)) if match else None,
            "decoder": first_line[0] if first_line else decoder.name,
            "decoder_sha256": hash_file(decoder),
            "command_redacted": [decoder.name, "--stdout", "--index", str(index), "--unit-rotation", "deg/s", path.name]}


def read_csv(path: Path) -> tuple[pd.DataFrame, dict[str, str]]:
    frame = pd.read_csv(path, skipinitialspace=True, low_memory=False)
    units = {}
    names = []
    for raw_name in frame.columns:
        match = re.fullmatch(r"\s*([^()]+?)(?:\s*\(([^)]+)\))?\s*", raw_name)
        if not match:
            raise InputError(f"Unrecognized CSV column: {raw_name}")
        name = match.group(1).strip()
        if name in names:
            raise InputError(f"Duplicate canonical CSV column: {name}")
        names.append(name)
        if match.group(2):
            units[name] = match.group(2).strip()
    frame.columns = names
    for name in names:
        if name not in {"flightModeFlags", "stateFlags", "failsafePhase"}:
            frame[name] = pd.to_numeric(frame[name], errors="coerce")
    return frame, units


def number(value: str):
    try:
        result = float(value)
        if not math.isfinite(result):
            return value
        return int(result) if result.is_integer() else result
    except ValueError:
        return value


def firmware_version(value: str) -> str | None:
    match = re.search(r"Betaflight(?:\s*/[^\r\n]*?)?\s+(\d+\.\d+(?:\.\d+)?)", value)
    return match.group(1) if match else None


def parse_config(path: Path, profile: int | None = None) -> dict:
    text = path.read_text(encoding="utf-8-sig")
    global_values: dict = {}
    profiles: dict[int, dict] = {}
    selected = None
    for line in text.splitlines():
        profile_match = re.fullmatch(r"\s*profile\s+(\d+)\s*", line)
        if profile_match:
            selected = int(profile_match.group(1))
            profiles.setdefault(selected, {})
            continue
        value_match = re.fullmatch(r"\s*set\s+([a-z0-9_]+)\s*=\s*(.*?)\s*", line)
        if value_match:
            target = global_values if selected is None else profiles[selected]
            target[value_match.group(1)] = number(value_match.group(2))
    if len(profiles) > 1 and profile is None:
        raise InputError("Config contains multiple PID profiles. Pass --profile with the zero-based CLI profile index.")
    if profile is not None and profiles and profile not in profiles:
        raise InputError(f"Profile {profile} was not found in the config.")
    picked = profile if profile is not None else next(iter(profiles), None)
    values = {**global_values, **profiles.get(picked, {})}
    return {"values": values, "profile": picked, "firmware": firmware_version(text),
            "source": "config_snapshot", "profiles_found": sorted(profiles)}


def config_from_headers(headers: dict[str, str]) -> dict:
    values = {key: number(value) for key, value in headers.items()
              if re.fullmatch(r"[a-z][a-z0-9_]+", key) and "," not in value}
    if "rpm_filter_weights" in headers:
        values["rpm_filter_weights"] = headers["rpm_filter_weights"]
    for axis in ("roll", "pitch", "yaw"):
        row = headers.get(axis + "PID", "").split(",")
        if len(row) == 3:
            values.update({f"{term}_{axis}": number(raw) for term, raw in zip(("p", "i", "d"), row)})
    for header, prefix in (("ff_weight", "f"), ("d_min", "d_min")):
        for axis, raw in zip(("roll", "pitch", "yaw"), headers.get(header, "").split(",")):
            if raw:
                values[f"{prefix}_{axis}"] = number(raw)
    for prefix in ("gyro", "dterm"):
        bounds = headers.get(f"{prefix}_lpf1_dyn_hz", "").split(",")
        if len(bounds) == 2:
            values[f"{prefix}_lpf1_dyn_min_hz"], values[f"{prefix}_lpf1_dyn_max_hz"] = map(number, bounds)
    for idx, raw in enumerate(headers.get("gyro_notch_hz", "").split(","), start=1):
        if raw:
            values[f"gyro_notch{idx}_hz"] = number(raw)
    for idx, raw in enumerate(headers.get("gyro_notch_cutoff", "").split(","), start=1):
        if raw:
            values[f"gyro_notch{idx}_cutoff"] = number(raw)
    bounds = headers.get("motorOutput", "").split(",")
    return {"values": values, "profile": None,
            "firmware": firmware_version(headers.get("Firmware revision", "")),
            "board": headers.get("Board information"), "source": "blackbox_header",
            "motor_output_bounds": [number(raw) for raw in bounds] if len(bounds) == 2 else None,
            "acc_1g": number(headers.get("acc_1G", ""))}
