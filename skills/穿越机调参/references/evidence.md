# 证据与版本边界

使用 Betaflight 的 [4.5.2 settings.c](https://github.com/betaflight/betaflight/blob/4.5.2/src/main/cli/settings.c) 核对名称、范围和枚举；用 [4.5.2 pid.c](https://github.com/betaflight/betaflight/blob/4.5.2/src/main/flight/pid.c) 理解 PID/TPA/Anti-gravity；用 [blackbox.c](https://github.com/betaflight/betaflight/blob/4.5.2/src/main/blackbox/blackbox.c) 核对记录字段。

`iterm_relax_type` 枚举为 GYRO=0、SETPOINT=1；简化模式与手动数值必须一致。GUI 的 D Max 对应 `d_*`，Derivative/基础 D 与 D-min 关系要按当前版本解释。

[RPM 官方指南](https://betaflight.com/docs/wiki/guides/current/DSHOT-RPM-Filtering) 与 [4.5 发布说明](https://betaflight.com/docs/wiki/release/Betaflight-4-5-Release-Notes) 用于操作背景，但不能把其中其他版本的参数直接套用。

[PIDtoolbox](https://github.com/bw1129/PIDtoolbox) 用于独立频谱/响应交叉检查；[Blackbox Explorer](https://github.com/betaflight/blackbox-log-viewer) 用于检查具体时域动作。Python 引擎的 coherence 是诊断指标，不是“0.25 即可证明可靠”的调参门槛。

复飞的油门/杆量分层只是减少混杂。桨、电池、重量、飞行模式、风和动作不同，都可能影响结果。机体 Z 加速度必须先经姿态变换才有可能讨论地面竖直方向；缺少该变换时不能断言高度振荡。

完整的逐主题一手资料和证据边界在仓库 `docs/research.md`，三次检测细节在 `docs/workflow.md`。这些仓库资料用于深入查证；安装后的技能自身仍提供必要约束与直接链接。
