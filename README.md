# 穿越机调参技能库 / FPV Tuning Skills

[English](README.en.md)

从黑盒记录到可审阅的 PID、滤波候选配置，默认完成 **三次真实飞行检测**。提供中文和英文技能入口，共用一个离线 Python 引擎。

目前能做：日志分段、采样与缺帧检查、连续窗频谱、低杆量频谱、油门覆盖、PID 跟随误差、RPM 遥测覆盖、电机输出边界、油门事件、复飞分层比较，以及完整/差异/回滚 CLI。

目前不能做：从任意一份黑盒证明“最佳 PID”、仅靠 body-Z 加速度认定垂直抖动、替代电机温度与机械检查、自动控制飞控写入。新引擎不等同于 PIDtoolbox 的阶跃响应算法。

## 三次检测

| 检测 | 输入 | 输出 | 下一步 |
| --- | --- | --- | --- |
| 1：基线 | 原始黑盒、当前 dump/diff、机型与症状 | 全项审查、PID＋滤波候选、回滚配置 | 应用选定候选后再飞 |
| 2：复查 | 第二次飞行黑盒、实际应用配置 | 匹配油门/杆量的比较、针对性修正 | 按修正方案再飞 |
| 3：验收 | 第三次飞行黑盒、温度与主观反馈 | 改善证据、剩余问题、保留/回退结论 | 有问题继续复测，不能自动判定成功 |

每次都同时审查 PID 与滤波，允许在一份方案里一起修改。三次是默认流程，可用 `--checks` 设置其他次数；不强制把 PID 和滤波分成不同飞行。

## 安装

需要 Python 3.10+。共享 Python 引擎在 `src/fpv_tune`，中文技能入口会在安装时带入一份运行代码；两者从同一来源生成。原始 `.bbl/.bfl` 另需用户自行提供兼容固件的 `blackbox_decode`，仓库不分发 PIDtoolbox 或解码器二进制。

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install ".[dev,plots]"
.\.venv\Scripts\python tools/install_skills.py
```

Linux/macOS 使用 `.venv/bin/python`。安装器将中英文技能放入 `$CODEX_HOME/skills`，未设置时使用 `~/.codex/skills`。更新已有同名技能加 `--update`，旧版本会备份到技能目录之外。英文技能使用安装后的 `fpv-tune` 命令；中文技能也带可直接调用的 `scripts/tune.py`。

日常安装使用上面的普通 wheel 安装，兼容包含中文的目录。开发时可在 ASCII 路径的 checkout 使用 `pip install -e ".[dev,plots]"`。

使用 `$穿越机调参` 或 `$fpv-drone-tuning`。技能以用户请求的语言回答；默认自动选择行为保持开启。

中文技能名保留既有调用习惯；只接受英文 hyphen-case 名称的客户端可使用英文入口。仓库校验器明确支持该中文名称，不修改上游校验器。

## 开始三次检测

```powershell
fpv-tune inspect --log flight-1.bbl
fpv-tune start --session outputs/my-build --checks 3
fpv-tune analyze --log flight-1.bbl --decoder /path/to/blackbox_decode.exe --session outputs/my-build --metadata flight-context.json --plots
```

激活虚拟环境或使用 `.venv/Scripts/fpv-tune.exe`。多段日志默认选字节数最大的一段，报告会记录选择依据；这不保证它就是最长或最适合调参的一段。用 `--index N` 明确指定；用 `--start-s/--end-s` 排除起降、碰撞等不适合的片段。

已解码 CSV 的时间列须带 `(us)`、`(ms)`、`(s)`，或指定 `--time-unit`；gyro 与 setpoint 应明确标注 `(deg/s)`，标注 `(rad/s)` 会转换成 deg/s。无 setpoint 单位时，只在已确认 Betaflight 4.5 非高分辨率格式下推断。CSV 输入可用 `--config dump.txt --profile 0` 补充实际配置。CLI profile 是 **0 起始**，GUI“PID 配置文件 1”对应 `profile 0`。

每次会输出 `analysis.json`、中英报告、`coverage.json` 和可选频谱图。再次对同一会话运行 `analyze` 会进入下一次检测，并比较上次数据；重复数据会被拒绝。

第三次还会生成对第一份基线的 `baseline-comparison.json` 和待填写的 `validation.json`，逐项记录通过、未通过或未覆盖；达到三次不等于自动验收。

## 生成完整候选配置

技能先解释症状与证据，再写 `changes.json`，每项必须有当前分析中真实存在的证据路径：

```json
{
  "changes": [
    {
      "key": "p_pitch",
      "value": 42,
      "reason": "Example only; replace with a conclusion supported by this flight's time traces.",
      "evidence": ["axes.pitch.tracking.normalized_mae"]
    }
  ]
}
```

此数值只是格式示例，不能当成任何机型的预设。

```powershell
fpv-tune plan --analysis outputs/my-build/check-1/analysis.json --config dump.txt --profile 0 --changes changes.json --out outputs/my-plan
```

输出 `candidate-cli.txt`、`full-reviewed-cli.txt`、`rollback-cli.txt`、`plan.json` 和中英说明。完整配置只包含真实记录且已支持的项目；未记录值列为 `needs_data`，不会补成默认值。明确要求保存命令时加 `--include-save`。

可执行 CLI 当前限定 **Betaflight 4.5.2** 的保守参数子集；其他固件可作数据检查，不生成可执行计划。手动改 PID/LPF 时会明确关闭对应的简化控制器，避免滑块重新计算覆盖数值。硬件、电机协议、接收机、failsafe、GPS 等不在计划写入范围。

## 资料与项目评估

- [原实现评估与修正](docs/assessment.md)
- [一手资料研究](docs/research.md) / [English Research](docs/research.en.md)
- [三次检测流程](docs/workflow.md) / [English Workflow](docs/workflow.en.md)
- [实现与证据边界](docs/methodology.md)

PIDtoolbox 适合频谱和响应核查，Blackbox Explorer 适合具体动作的时域检查，Betaflight App/CLI 用于读取和应用配置。它们仍需结合电机温度、DShot 错误和机械状态。[Betaflight RPM 指南](https://betaflight.com/docs/wiki/guides/current/DSHOT-RPM-Filtering)

## 验证与开发

```powershell
python -m pytest
python tools/validate_skills.py
python examples/generate_demo.py --out .local/demo
fpv-tune analyze --csv .local/demo/flight-1.csv --config .local/demo/dump.txt --profile 0 --out .local/demo/report --plots
```

测试涵盖断段频谱、时间单位、相同日志复用、配置 profile 隔离、枚举转换、简化模式、参数范围与回滚。合成演示由脚本生成，不包含个人飞行数据。仓库使用 MIT 许可，仅包含本项目代码与引用链接，未复制上游固件或 PIDtoolbox 实现。
