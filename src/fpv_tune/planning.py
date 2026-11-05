"""Compile explicitly reviewed proposals against a small, versioned CLI vocabulary."""

from __future__ import annotations

from dataclasses import dataclass

from .io import InputError


SOURCE = "https://github.com/betaflight/betaflight/blob/4.5.2/src/main/cli/settings.c"
SUPPORTED = {"4.5.2"}


@dataclass(frozen=True)
class Parameter:
    group: str
    scope: str = "profile"
    minimum: int = 0
    maximum: int = 250
    enums: tuple[str, ...] = ()
    array_length: int = 0

    def normalize(self, value):
        if self.array_length:
            try:
                items = [int(part.strip()) for part in value.split(",")] if isinstance(value, str) else list(value)
            except (TypeError, ValueError) as error:
                raise InputError("Expected a bounded integer array") from error
            if len(items) != self.array_length or any(not isinstance(item, int) or isinstance(item, bool) or not self.minimum <= item <= self.maximum for item in items):
                raise InputError("Invalid array length or value")
            return ",".join(str(item) for item in items)
        if self.enums:
            if isinstance(value, int) and not isinstance(value, bool) and 0 <= value < len(self.enums):
                return self.enums[value]
            if isinstance(value, str) and value.upper() in self.enums:
                return value.upper()
            raise InputError(f"Expected one of {self.enums}, got {value!r}")
        if not isinstance(value, int) or isinstance(value, bool) or not self.minimum <= value <= self.maximum:
            raise InputError(f"Expected an integer in project-supported interval {self.minimum}..{self.maximum}, got {value!r}")
        return value


def registry() -> dict[str, Parameter]:
    rules = {}
    for axis in ("roll", "pitch", "yaw"):
        for term in ("p", "i", "d", "d_min"):
            rules[f"{term}_{axis}"] = Parameter("PID")
        rules[f"f_{axis}"] = Parameter("Feedforward", maximum=1000)
    for prefix, group, scope in (("gyro", "Gyro LPF", "global"), ("dterm", "D-term LPF", "profile")):
        for key in ("lpf1_static_hz", "lpf1_dyn_min_hz", "lpf1_dyn_max_hz", "lpf2_static_hz"):
            rules[f"{prefix}_{key}"] = Parameter(group, scope=scope, maximum=1000)
        for key in ("lpf1_type", "lpf2_type"):
            rules[f"{prefix}_{key}"] = Parameter(group, scope=scope, enums=("PT1", "BIQUAD", "PT2", "PT3"))
        rules[f"{prefix}_lpf1_dyn_expo"] = Parameter(group, scope=scope, maximum=10)
    for idx in (1, 2):
        for key in ("hz", "cutoff"):
            rules[f"gyro_notch{idx}_{key}"] = Parameter("Static gyro notch", scope="global", maximum=1000)
    for key in ("hz", "cutoff"):
        rules[f"dterm_notch_{key}"] = Parameter("D-term notch", maximum=1000)
    for key, maximum in (("count", 5), ("q", 1000), ("min_hz", 1000), ("max_hz", 1000)):
        rules[f"dyn_notch_{key}"] = Parameter("Dynamic notch", scope="global", maximum=maximum)
    for key, maximum in (("harmonics", 3), ("q", 1000), ("min_hz", 1000), ("lpf_hz", 500)):
        rules[f"rpm_filter_{key}"] = Parameter("RPM filter", scope="global", maximum=maximum)
    for key, maximum in (("d_max_gain", 100), ("d_max_advance", 200), ("yaw_lowpass_hz", 500),
                         ("anti_gravity_gain", 250), ("anti_gravity_p_gain", 250),
                         ("anti_gravity_cutoff_hz", 50), ("iterm_relax_cutoff", 50),
                         ("feedforward_smooth_factor", 95), ("feedforward_jitter_factor", 20),
                         ("feedforward_boost", 50), ("feedforward_max_rate_limit", 100),
                         ("feedforward_transition", 100), ("tpa_rate", 100),
                         ("tpa_breakpoint", 2000), ("tpa_low_rate", 100),
                         ("tpa_low_breakpoint", 2000), ("throttle_boost", 100),
                         ("throttle_boost_cutoff", 50), ("dyn_idle_min_rpm", 200)):
        rules[key] = Parameter("TPA / throttle" if key.startswith(("tpa_", "throttle_")) else "Other control", maximum=maximum)
    rules["iterm_relax"] = Parameter("Other control", enums=("OFF", "RP", "RPY", "RP_INC", "RPY_INC"))
    rules["iterm_relax_type"] = Parameter("Other control", enums=("GYRO", "SETPOINT"))
    rules["tpa_mode"] = Parameter("TPA / throttle", enums=("PD", "D"))
    rules["feedforward_averaging"] = Parameter("Feedforward", enums=("OFF", "2_POINT", "3_POINT", "4_POINT"))
    rules["tpa_low_always"] = Parameter("TPA / throttle", enums=("OFF", "ON"))
    rules["simplified_pids_mode"] = Parameter("Simplified controls", enums=("OFF", "RP", "RPY"))
    for key in ("simplified_gyro_filter", "simplified_dterm_filter"):
        rules[key] = Parameter("Simplified controls", "global" if "gyro" in key else "profile", enums=("OFF", "ON"))
    for key in ("master_multiplier", "i_gain", "d_gain", "pi_gain", "dmax_gain", "feedforward_gain",
                "pitch_d_gain", "pitch_pi_gain", "dterm_filter_multiplier", "gyro_filter_multiplier"):
        rules[f"simplified_{key}"] = Parameter("Simplified controls", "global" if "gyro" in key else "profile", maximum=200)
    # Narrow project-supported intervals must remain inside the tagged firmware's ranges.
    for key, low, high in (
        ("dyn_notch_q", 1, 1000), ("dyn_notch_min_hz", 20, 250), ("dyn_notch_max_hz", 200, 1000),
        ("rpm_filter_q", 250, 1000), ("rpm_filter_min_hz", 30, 200), ("rpm_filter_lpf_hz", 100, 500),
        ("tpa_breakpoint", 1000, 2000), ("tpa_low_breakpoint", 1000, 2000),
        ("anti_gravity_cutoff_hz", 2, 50), ("iterm_relax_cutoff", 1, 50), ("throttle_boost_cutoff", 5, 50),
        ("simplified_gyro_filter_multiplier", 10, 200), ("simplified_dterm_filter_multiplier", 10, 200),
    ):
        previous = rules[key]
        rules[key] = Parameter(previous.group, previous.scope, low, high)
    rules["rpm_filter_weights"] = Parameter("RPM filter", "global", maximum=100, array_length=3)
    rules["rpm_filter_fade_range_hz"] = Parameter("RPM filter", "global", maximum=1000)
    return rules


def normalize_known(values: dict) -> tuple[dict, dict]:
    known, unsupported = {}, {}
    for key, value in values.items():
        rule = registry().get(key)
        if rule:
            try:
                known[key] = rule.normalize(value)
            except InputError as error:
                unsupported[key] = str(error)
    return known, unsupported


def review_table(snapshot: dict) -> list[dict]:
    if snapshot.get("firmware") not in SUPPORTED:
        return [{"key": key, "group": rule.group, "scope": rule.scope,
                 "current": snapshot.get("values", {}).get(key), "status": "unverified_version"}
                for key, rule in registry().items()]
    known, unsupported = normalize_known(snapshot.get("values", {}))
    return [{"key": key, "group": rule.group, "scope": rule.scope,
             "current": known.get(key), "status": "needs_review" if key in unsupported else "observed" if key in known else "not_recorded"}
            for key, rule in registry().items()]


def compile_plan(analysis: dict, config_snapshot: dict, changes: dict, profile: int,
                 include_save: bool = False) -> dict:
    if analysis.get("schema_version") != 2:
        raise InputError("Re-analyze the log with the current tool before planning.")
    version = analysis["config"].get("firmware")
    if version not in SUPPORTED or config_snapshot.get("firmware") != version:
        raise InputError("Executable plans currently require matching Betaflight 4.5.2 log and config snapshot. Other versions are analysis-only.")
    blockers = analysis["quality"].get("planning_blockers", [])
    if blockers:
        raise InputError(f"Planning blocked by log quality: {', '.join(blockers)}")
    if config_snapshot.get("profile") not in (None, profile):
        raise InputError("Selected profile does not match the config snapshot.")
    if analysis["config"].get("profile") not in (None, profile):
        raise InputError("Selected profile does not match the analyzed flight profile.")
    current, unsupported = normalize_known(config_snapshot["values"])
    observed, _ = normalize_known(analysis["config"]["values"])
    stale = [key for key in current.keys() & observed.keys() if current[key] != observed[key]]
    if stale:
        raise InputError(f"Config does not match the analyzed flight: {', '.join(sorted(stale))}. Analyze a flight using this configuration.")
    proposals = changes.get("changes")
    if not isinstance(proposals, list):
        raise InputError("Proposal JSON must contain a changes list.")
    target = current.copy()
    rows = []
    seen = set()
    rules = registry()
    for entry in proposals:
        if not isinstance(entry, dict):
            raise InputError("Each proposal must be an object.")
        key = entry.get("key")
        if key not in rules or key in seen:
            raise InputError(f"Unknown or duplicate parameter: {key}")
        seen.add(key)
        if key not in current:
            raise InputError(f"Current value missing or unsupported: {key}; {unsupported.get(key, 'supply a config snapshot')}")
        if not isinstance(entry.get("reason"), str) or not entry["reason"].strip():
            raise InputError(f"Proposal needs a reason: {key}")
        evidence = entry.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            raise InputError(f"Proposal needs analysis metric paths: {key}")
        for pointer in evidence:
            node = analysis
            try:
                for part in pointer.split("."):
                    node = node[part]
            except (KeyError, TypeError, AttributeError) as error:
                raise InputError(f"Unknown evidence metric path: {pointer}") from error
            if node is None:
                raise InputError(f"Evidence metric is unavailable: {pointer}")
        new = rules[key].normalize(entry.get("value"))
        if new == current[key]:
            continue
        if key in {f"{term}_{axis}" for axis in ("roll", "pitch", "yaw") for term in ("d", "d_min")} and isinstance(new, int) and new > current[key]:
            axis = key.rsplit("_", 1)[1]
            if analysis["axes"].get(axis, {}).get("dterm", {}).get("status") != "measured":
                raise InputError(f"D increase requires measured {axis} D-term data.")
        if key in {"d_max_gain", "d_max_advance"} and new > current[key]:
            active_axes = [axis for axis in ("roll", "pitch", "yaw") if current.get(f"d_{axis}", 0) > 0]
            if not active_axes or any(analysis["axes"].get(axis, {}).get("dterm", {}).get("status") != "measured" for axis in active_axes):
                raise InputError("Dynamic-D sensitivity increase requires measured D-term on its active axes.")
        rows.append({"key": key, "before": current[key], "after": new,
                     "reason": entry["reason"], "evidence": evidence, "status": "candidate_not_flight_validated"})
        target[key] = new
    pid_keys = {f"{term}_{axis}" for axis in ("roll", "pitch", "yaw") for term in ("p", "i", "d", "d_min", "f")}
    pid_direct = bool(seen & pid_keys)
    gyro_direct = any(key.startswith("gyro_lpf") for key in seen)
    dterm_direct = any(key.startswith("dterm_lpf") for key in seen)
    automatic = []
    for active, key in ((pid_direct, "simplified_pids_mode"),
                        (gyro_direct, "simplified_gyro_filter"), (dterm_direct, "simplified_dterm_filter")):
        if active and key in seen and target[key] != "OFF":
            raise InputError(f"Manual parameters conflict with enabled {key}.")
        if active and current.get(key) not in (None, "OFF"):
            automatic.append(key)
            target[key] = "OFF"
    pid_sliders = {key for key in rules if key.startswith("simplified_") and "filter" not in key and key != "simplified_pids_mode"}
    for active, conflicting in ((pid_direct, pid_sliders),
                                (gyro_direct, {"simplified_gyro_filter_multiplier"}),
                                (dterm_direct, {"simplified_dterm_filter_multiplier"})):
        if active and seen & conflicting:
            raise InputError("Do not combine manual PID values with simplified multipliers in one plan.")
    for axis in ("roll", "pitch", "yaw"):
        if f"d_min_{axis}" in target and f"d_{axis}" in target and target[f"d_min_{axis}"] > target[f"d_{axis}"]:
            raise InputError(f"D-min exceeds D Max for {axis}.")
    for prefix in ("gyro", "dterm"):
        low, high = target.get(f"{prefix}_lpf1_dyn_min_hz"), target.get(f"{prefix}_lpf1_dyn_max_hz")
        if low is not None and high is not None and low > high and high != 0:
            raise InputError(f"{prefix} dynamic low-pass minimum exceeds maximum.")
    if target.get("dyn_notch_min_hz", 0) > target.get("dyn_notch_max_hz", 1000):
        raise InputError("Dynamic-notch minimum exceeds maximum.")
    for key in automatic:
        if not any(row["key"] == key for row in rows):
            rows.append({"key": key, "before": current[key], "after": "OFF",
                         "reason": "Preserve explicit manual values against later simplified-slider recalculation.",
                         "evidence": [], "status": "mode_consistency_change"})
    changed = {row["key"]: row["after"] for row in rows}

    def cli(values: dict, save: bool) -> str:
        lines = ["# Reviewed candidate for Betaflight 4.5.2", f"profile {profile}"]
        # Disable simplified controllers before writing their manual values.
        ordered = sorted(values, key=lambda key: (0 if key in automatic else 1, key))
        lines += [f"set {key} = {values[key]}" for key in ordered]
        if save:
            lines.append("save")
        else:
            lines.append("# Review the CLI response before issuing save.")
        return "\n".join(lines) + "\n"

    coverage = review_table(config_snapshot)
    for row in coverage:
        row["recommended"] = target.get(row["key"])
        row["decision"] = "change_candidate" if row["key"] in changed else "hold_observed" if row["status"] == "observed" else "needs_data"
    return {"schema_version": 2, "firmware": version, "profile": profile,
            "status": "candidate_not_flight_validated", "changes": rows, "coverage": coverage,
            "source": SOURCE, "analysis_sha256": analysis["source"]["sha256"],
            "candidate_cli": cli(changed, include_save),
            "rollback_cli": cli({key: current[key] for key in changed}, include_save),
            "full_cli": cli(target, include_save),
            "omitted_unrecorded": [row["key"] for row in coverage if row["status"] != "observed"]}
