# 三次检测：从基线到验收

[English](workflow.en.md)

## 第一次检测：完整基线和联合方案

接收原始日志、活动 PID profile 的配置、机型/桨/电池/重量、问题发生的时间或动作。定位有效飞行段，检查解码错误、时间轴、字段、单位、模式和可用带宽。原始 gyro 谱可能已有日志抽取混叠，不能简单当作实时传感器全带宽。

同时审查 P/I/D、动态 D、FF、gyro 与 D-term 两级低通、RPM/动态陷波/静态陷波、TPA、I-term Relax、Anti-gravity 与油门设置。给每项“候选修改 / 保持 / 待补证据”。不要为了让所有数字变化而调整正常参数。

候选可以同时改 PID 和滤波。每个改动有理由和实际指标/事件依据，关联适用工况，生成完整配置、差异 CLI 和回滚。修改后的小范围复飞用于核对，而不是由程序声称通过。

## 第二次检测：新飞行数据复查

确认实际应用的参数，使用新日志进入同一会话。比较相同硬件与模式，在油门/杆量相近的连续窗里对比跟随、D 噪声、电机余量、RPM 覆盖与症状事件。记录与上次不同的桨、电池、负载、风和飞行动作。

只有实际数据支持时保留改动。若改善不明确或出现退化，可以回退部分或整套方案。两种修改同时发生时，报告整套方案的观察性变化，不能唯一归因于其中一个参数。

## 第三次检测：验收与剩余问题

使用第二次修订后的第三份日志，结合独立动作、实际用途、电机温度与反馈，逐项记录“通过 / 未通过 / 未覆盖”。改善应在对应工况复现；没有覆盖高油门、急停或尾流就注明未覆盖。

程序到三次后只记录 `checks_analyzed_review_required`，不写“已调好”。技能需要解释验收证据和剩余事项；若有剩余问题，则进入新的后续会话。

## 输入示例

下面字段由操作者填写，未知就留空或省略：

```json
{
  "airframe_id": "my-build",
  "props": "actual-prop-model",
  "battery_cells": 6,
  "flight_mode": "ACRO",
  "mass_g": 650,
  "motor_temperature_c": null,
  "wind_notes": "record actual conditions"
}
```

温度缺失时不能宣称温度合格。`airframe_id` 等可含个人标识，默认保留本地。

## 各阶段命令

```sh
fpv-tune start --session outputs/my-build --checks 3
fpv-tune analyze --log flight-1.bbl --decoder /path/to/blackbox_decode --session outputs/my-build --metadata context-1.json --symptom "throttle wobble" --plots
fpv-tune plan --analysis outputs/my-build/check-1/analysis.json --config dump-1.txt --profile 0 --changes changes-1.json --out outputs/plan-1
fpv-tune analyze --log flight-2.bbl --decoder /path/to/blackbox_decode --session outputs/my-build --metadata context-2.json --plots
fpv-tune plan --analysis outputs/my-build/check-2/analysis.json --config dump-2.txt --profile 0 --changes changes-2.json --out outputs/plan-2
fpv-tune analyze --log flight-3.bbl --decoder /path/to/blackbox_decode --session outputs/my-build --metadata context-3.json --plots
```

命令只处理文件；应用 CLI 和实际飞行由操作者执行。可以要求 `--include-save`，但参数计划生成不会自动接入飞控。
