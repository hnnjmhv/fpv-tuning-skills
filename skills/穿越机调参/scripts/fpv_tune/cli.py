"""Portable command line entrypoints; all operations produce local artifacts only."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .analysis import AXES, analyze, compare
from .io import (InputError, config_from_headers, decode, hash_file, list_logs,
                 parse_config, read_csv, select_log)
from .planning import compile_plan, review_table


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise InputError(f"Expected a JSON object: {path.name}")
    return value


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def fresh_dir(path: Path) -> None:
    if path.exists() and (not path.is_dir() or any(path.iterdir())):
        raise InputError(f"Output must be a new or empty directory: {path}")
    path.mkdir(parents=True, exist_ok=True)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="fpv-tune", description="Blackbox measurements, three-flight checks and reviewed PID/filter plans.")
    root.add_argument("--version", action="version", version=__version__)
    sub = root.add_subparsers(dest="command", required=True)
    inspect = sub.add_parser("inspect", help="List log sections without running a decoder")
    inspect.add_argument("--log", type=Path, required=True)
    start = sub.add_parser("start", help="Create a journal for three real flight checks")
    start.add_argument("--session", type=Path, required=True)
    start.add_argument("--checks", type=int, default=3)
    run = sub.add_parser("analyze", help="Analyze one new flight; generate Chinese and English reports")
    source = run.add_mutually_exclusive_group(required=True)
    source.add_argument("--log", type=Path)
    source.add_argument("--csv", type=Path)
    target = run.add_mutually_exclusive_group(required=True)
    target.add_argument("--out", type=Path)
    target.add_argument("--session", type=Path)
    run.add_argument("--check", type=int)
    run.add_argument("--decoder", type=Path)
    run.add_argument("--index", type=int)
    run.add_argument("--config", type=Path)
    run.add_argument("--profile", type=int)
    run.add_argument("--firmware", help="CSV only, for example 4.5.2; not a substitute for a matching config")
    run.add_argument("--time-unit", choices=("us", "ms", "s"))
    run.add_argument("--metadata", type=Path, help="Airframe, props, battery and flight context JSON")
    run.add_argument("--symptom", action="append", default=[])
    run.add_argument("--window-seconds", type=float, default=1.0)
    run.add_argument("--start-s", type=float)
    run.add_argument("--end-s", type=float)
    run.add_argument("--plots", action="store_true")
    comparison = sub.add_parser("compare", help="Compare matched throttle/command windows from two analyses")
    comparison.add_argument("--before", type=Path, required=True)
    comparison.add_argument("--after", type=Path, required=True)
    comparison.add_argument("--out", type=Path, required=True)
    plan = sub.add_parser("plan", help="Compile an explicit evidence-backed proposal into full/diff/rollback CLI")
    plan.add_argument("--analysis", type=Path, required=True)
    plan.add_argument("--config", type=Path, required=True)
    plan.add_argument("--profile", type=int, required=True, help="Zero-based Betaflight CLI profile index")
    plan.add_argument("--changes", type=Path, required=True)
    plan.add_argument("--out", type=Path, required=True)
    plan.add_argument("--include-save", action="store_true")
    return root


def write_analysis_reports(out: Path, report: dict) -> None:
    q = report["quality"]
    snapshot = report["config"]
    coverage = review_table(snapshot)
    write_json(out / "coverage.json", {"parameters": coverage})
    for lang in ("zh-CN", "en"):
        zh = lang == "zh-CN"
        lines = ["# 穿越机 PID 与滤波检测" if zh else "# FPV PID and filter check", "",
                 ("状态：测量完成，参数修改尚未实飞验证。" if zh else "Status: measured; parameter changes are not flight-validated."), "",
                 f"Firmware: {snapshot.get('firmware') or 'unknown'}",
                 f"Log: {report['source']['name']} / index {report['source'].get('index', 'CSV')}",
                 f"SHA256: `{report['source']['sha256']}`",
                 f"Flight check: {report.get('flight_check', {}).get('number', 1)} / {report.get('flight_check', {}).get('planned', 1)} ({report.get('flight_check', {}).get('phase', 'single')})",
                 f"Sample rate: {report['timing']['sample_rate_hz']:.2f} Hz; duration: {report['timing']['duration_s']:.2f} s",
                 f"Contiguous windows: {q['flight_windows']}; low-setpoint windows: {q['low_setpoint_windows']}", "",
                 "## 数据质量" if zh else "## Data Quality", ""]
        lines.extend(f"- {item}" for item in q["planning_blockers"] + q["warnings"])
        if not q["planning_blockers"]:
            lines.append("- 基本时间轴检查通过；不等于调参或适航验收通过。" if zh else "- Basic timing checks passed; this does not validate the tune or flight readiness.")
        lines += ["", "## PID、滤波与控制项目" if zh else "## PID, Filters and Controls", "",
                  "| Group | Parameter | Scope | Logged Value | Status |", "| --- | --- | --- | --- | --- |"]
        lines.extend(f"| {row['group']} | `{row['key']}` | {row['scope']} | {row['current'] if row['current'] is not None else '?'} | {row['status']} |" for row in coverage)
        lines += ["", "## 测量与证据边界" if zh else "## Measurements and Limits", ""]
        for axis in AXES:
            details = report["axes"][axis]
            tracking = details["tracking"]
            lines.append(f"- {axis}: rate MAE = {tracking.get('mae_deg_s', 'n/a')} deg/s; normalized MAE = {tracking.get('normalized_mae', 'n/a')}; {tracking['status']}")
            for signal in ("gyro_post", "gyro_pre", "dterm"):
                metric = details[signal]
                lines.append(f"- {axis} {signal}: {metric['status']}; units = {metric.get('unit', '?')}; 180-450 Hz RMS = {metric.get('band_rms', {}).get('180_450', 'n/a')}")
        lines += ["", "## 油门与后续判断" if zh else "## Throttle and Interpretation", ""]
        if zh:
            lines += ["- 高频 RMS 没有通用的安全阈值；D-term 单位还受当前增益影响。",
                      "- RPM 设置开启只证明配置存在，遥测有效性与 DShot 错误需要单独核查。",
                      "- 推油门事件中的机体 Z 加速度包含姿态和推力变化，不能直接当作地面坐标的上下抖动。",
                      "- 跟随误差不能单独决定加 P/I/FF；检查目标速率、gyro、PID 项和电机时域片段。",
                      "- 可在一次方案中合并 PID 与滤波修改；每项填写 reason 和真实 evidence 路径。",
                      "- 三次检测依次使用三份真实飞行数据；最后一次仍有问题时记录待复测，不自动宣称调好。"]
        else:
            lines += ["- There is no universal safe high-frequency RMS threshold; D-term units also depend on gains.",
                      "- RPM enable flags do not establish valid telemetry or a zero DShot error rate.",
                      "- Body Z acceleration during a throttle punch includes attitude and thrust changes; it is not earth-frame vertical motion.",
                      "- Tracking error alone does not determine a P/I/FF increase; inspect time-aligned setpoint, gyro, PID and motor traces.",
                      "- PID and filters may be proposed together; each change needs a reason and actual evidence paths.",
                      "- The three checks require three actual flights. Remaining problems require another test, not an automatic tuned claim."]
        if report.get("symptoms"):
            lines += ["", "Reported symptoms:", *[f"- {s}" for s in report["symptoms"]]]
        (out / f"report.{lang}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_comparison(out: Path, comparison: dict, prefix: str = "comparison") -> None:
    write_json(out / f"{prefix}.json", comparison)
    for lang in ("zh-CN", "en"):
        lines = ["# 复飞对比（观察性结果）" if lang == "zh-CN" else "# Flight Comparison (Observational)", "",
                 comparison["interpretation"], "", *[f"- {s}" for s in comparison["warnings"]], "",
                 "| Throttle Bin | Command Bin | Before Windows | After Windows |", "| --- | --- | --- | --- |"]
        lines += [f"| {row['throttle_bin']} | {row['setpoint_bin']} | {row['before_windows']} | {row['after_windows']} |" for row in comparison["common_strata"]]
        lines += ["", "Parameter differences:", "", *[f"- `{key}`: {value['before']} -> {value['after']}" for key, value in comparison["config_changes"].items()]]
        (out / f"{prefix}.{lang}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_plots(out: Path, plot_data: dict) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    figure, axes = plt.subplots(3, 3, figsize=(15, 10), squeeze=False)
    for row, axis in enumerate(AXES):
        for col, kinds in enumerate((("gyro_pre",), ("gyro_post",), ("dterm",))):
            panel = axes[row, col]
            for name in kinds:
                data = plot_data[axis].get(name)
                if data and len(data["density"]):
                    # Raw pre-filter units are deliberately not presented as normalized attenuation.
                    panel.semilogy(data["frequency"], data["density"] + 1e-18,
                                   label=f"{name} ({data['unit']})")
            available = [data["frequency"][-1] for data in plot_data[axis].values() if len(data["frequency"])]
            panel.set_xlim(20, min(900, max(available, default=900)))
            panel.set_title(f"{axis}: {kinds[0]}")
            panel.set_xlabel("Frequency (Hz)")
            panel.set_ylabel("PSD [signal-unit squared / Hz]")
            panel.grid(alpha=0.2)
            if panel.lines:
                panel.legend(fontsize=8)
            else:
                panel.text(0.5, 0.5, "Not recorded / insufficient data", ha="center", va="center", transform=panel.transAxes)
    figure.tight_layout()
    figure.savefig(out / "spectra.png", dpi=130)
    plt.close(figure)


def run_analyze(args) -> None:
    session = None
    check = None
    if args.session:
        session_path = args.session / "session.json"
        if not session_path.is_file():
            raise InputError("Run fpv-tune start --session PATH first.")
        session = read_json(session_path)
        check = len(session["checks"]) + 1
        if args.check is not None and args.check != check:
            raise InputError(f"Expected check {check}; completed checks cannot be overwritten.")
        if check > session["checks_planned"]:
            raise InputError("All scheduled checks are analyzed; start a follow-up session for additional flights.")
        out = args.session / f"check-{check}"
    else:
        if args.check is not None:
            raise InputError("--check requires --session.")
        out = args.out
    selected = None
    snapshot = {"values": {}, "firmware": args.firmware, "profile": None, "board": None}
    if args.log:
        if not args.decoder:
            raise InputError("Raw blackbox input requires --decoder; the repository does not bundle executables.")
        selected = select_log(list_logs(args.log), args.index)
        snapshot = config_from_headers(selected["headers"])
        source = {"name": args.log.name, "sha256": selected["sha256"], "index": selected["index"],
                  "selection": "explicit_index" if args.index else "largest_section_by_bytes", "size_bytes": selected["size_bytes"]}
    else:
        source = {"name": args.csv.name, "sha256": hash_file(args.csv), "index": None}
    if session and any(row["sha256"] == source["sha256"] for row in session["checks"]):
        raise InputError("This content is already in the session. A new check requires a new flight log.")
    if args.config:
        supplied = parse_config(args.config, args.profile)
        if snapshot.get("firmware") and supplied.get("firmware") and supplied["firmware"] != snapshot["firmware"]:
            raise InputError("Config firmware does not match the log.")
        if args.log:
            # An after-flight config cannot silently overwrite the configuration actually flown.
            from .planning import normalize_known
            logged, _ = normalize_known(snapshot["values"])
            current, _ = normalize_known(supplied["values"])
            if any(logged[key] != current[key] for key in logged.keys() & current.keys()):
                raise InputError("Config settings differ from the blackbox header. Use the configuration that was flown.")
        snapshot["values"] = {**snapshot["values"], **supplied["values"]}
        snapshot["profile"] = supplied["profile"]
        snapshot["firmware"] = supplied["firmware"] or snapshot.get("firmware")
    fresh_dir(out)
    csv_path = args.csv
    if args.log:
        csv_path = out / "decoded.csv"
        source["decoder"] = decode(args.log, args.decoder, selected["index"], csv_path)
    frame, units = read_csv(csv_path)
    if args.start_s is not None or args.end_s is not None:
        if args.start_s is None or args.end_s is None or args.end_s <= args.start_s or args.start_s < 0:
            raise InputError("Provide both --start-s and --end-s with 0 <= start < end.")
        trim = (args.start_s, args.end_s)
    else:
        trim = None
    metadata = read_json(args.metadata) if args.metadata else {}
    report, plots = analyze(frame, units, snapshot, source, args.time_unit, args.window_seconds, metadata, trim)
    report["tool_version"] = __version__
    report["symptoms"] = args.symptom
    planned = session["checks_planned"] if session else 1
    phase = "single" if session is None else "baseline" if check == 1 else "evaluation" if check == planned else "recheck"
    report["flight_check"] = {"number": check or 1, "planned": planned, "phase": phase}
    write_json(out / "analysis.json", report)
    write_analysis_reports(out, report)
    if args.plots:
        write_plots(out, plots)
    if session is not None:
        previous = session["checks"][-1] if session["checks"] else None
        if previous:
            before = read_json(args.session / previous["analysis"])
            try:
                comparison = compare(before, report)
                write_comparison(out, comparison)
            except InputError as error:
                write_json(out / "comparison-unavailable.json", {"reason": str(error)})
        if len(session["checks"]) >= 2:
            baseline = read_json(args.session / session["checks"][0]["analysis"])
            try:
                write_comparison(out, compare(baseline, report), prefix="baseline-comparison")
            except InputError as error:
                write_json(out / "baseline-comparison-unavailable.json", {"reason": str(error)})
        if check == planned:
            write_json(out / "validation.json", {"status": "review_required", "validated": False,
                "criteria": {key: {"status": "not_evaluated", "evidence": []}
                             for key in ("tracking", "filter_noise", "throttle_symptoms", "rpm_telemetry", "motor_temperature", "intended_use")},
                "interpretation": "Fill pass/fail/not_covered from actual evidence and operator feedback; the scheduled count does not imply success."})
        session["checks"].append({"check": check, "sha256": source["sha256"], "analysis": f"check-{check}/analysis.json",
                                  "quality_blockers": report["quality"]["planning_blockers"]})
        session["status"] = "awaiting_new_flight" if check < session["checks_planned"] else "checks_analyzed_review_required"
        write_json(args.session / "session.json", session)
    print(f"Analysis: {out / 'analysis.json'}")
    print(f"Bilingual reports: {out}")


def run_plan(args) -> None:
    if not 0 <= args.profile <= 2:
        raise InputError("Betaflight 4.5.2 CLI profile index must be 0, 1 or 2.")
    result = compile_plan(read_json(args.analysis), parse_config(args.config, args.profile), read_json(args.changes), args.profile, args.include_save)
    fresh_dir(args.out)
    write_json(args.out / "plan.json", result)
    for name, key in (("candidate-cli.txt", "candidate_cli"), ("rollback-cli.txt", "rollback_cli"), ("full-reviewed-cli.txt", "full_cli")):
        (args.out / name).write_text(result[key], encoding="utf-8")
    for lang in ("zh-CN", "en"):
        lines = ["# PID 与滤波候选方案" if lang == "zh-CN" else "# PID and Filter Candidate Plan", "", result["status"], "",
                 "| Key | Before | Candidate | Reason |", "| --- | --- | --- | --- |"]
        lines += [f"| `{row['key']}` | {row['before']} | {row['after']} | {row['reason']} |" for row in result["changes"]]
        lines += ["", "Missing / unsupported values omitted from executable CLI:", *[f"- `{key}`" for key in result["omitted_unrecorded"]]]
        (args.out / f"plan.{lang}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Candidate / full / rollback CLI: {args.out}")


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "inspect":
            print(json.dumps(list_logs(args.log), ensure_ascii=False, indent=2))
        elif args.command == "start":
            if args.checks < 1:
                raise InputError("--checks must be positive.")
            fresh_dir(args.session)
            write_json(args.session / "session.json", {"schema_version": 2, "checks_planned": args.checks,
                       "checks": [], "status": "awaiting_baseline_flight", "validated": False})
            print(f"Created session for {args.checks} actual flight checks.")
        elif args.command == "analyze":
            run_analyze(args)
        elif args.command == "compare":
            result = compare(read_json(args.before), read_json(args.after))
            fresh_dir(args.out)
            write_comparison(args.out, result)
            print(f"Comparison: {args.out}")
        elif args.command == "plan":
            run_plan(args)
        return 0
    except (InputError, OSError, json.JSONDecodeError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
