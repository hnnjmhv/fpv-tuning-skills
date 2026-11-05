---
name: 穿越机调参
description: 分析穿越机 Betaflight 黑盒日志，审查 PID 与滤波并生成有依据的完整候选配置；默认使用三次真实飞行数据复查和收敛，也支持单次完整分析。
---

# 穿越机调参

用户要完整方案时，同时审查 PID、D-min/D Max、FF、Gyro/D-term LPF1/LPF2、RPM、动态与静态陷波、TPA、I-term Relax、Anti-gravity 和油门控制。根据数据提出必要改动，其余标注保持或缺少证据。不要为让界面变化而改参数。

## 资料与工具

使用本技能的 `scripts/tune.py`，或环境中的 `fpv-tune`。依赖与中英手册随 GitHub 仓库提供。运行时从当前技能路径定位脚本，不使用作者机器的绝对路径。原始日志需用户提供兼容的 `blackbox_decode`；CSV 可以直接分析。

安装器会在本机 `scripts/runtime.json` 记录所用 Python 和模块入口。已安装时优先用该解释器；仓库中没有此本机文件时，选择已装好依赖的环境。该文件含本机路径，不应提交 Git。

先读 [references/evidence.md](references/evidence.md)，再解释数据或选参数。上游文档可能包含旧固件建议，CLI 名称与枚举优先核对实际固件的源码/参考。

## 三次真实飞行检测

1. 基线：读取日志、机型、当前配置与症状；一次审查 PID＋滤波，输出完整候选、差异和回滚配置。
2. 复查：应用选定参数后录新日志，比较实际配置与相近油门/杆量窗口；保留、修正或回退。
3. 验收：第三份新日志结合电机温度与飞行反馈，记录改善和剩余问题。仍有问题则继续复测。

三次是默认次数，可按用户要求调整；单次请求不强迫等待复飞。使用同一份日志重算不能作为新检测。每次允许一起改 PID 和滤波，需说明多项同时变化限制因果归因。

```sh
fpv-tune start --session outputs/build --checks 3
fpv-tune inspect --log flight-1.bbl
fpv-tune analyze --log flight-1.bbl --decoder /path/to/blackbox_decode --session outputs/build --plots
```

后两次对同一会话传入新的日志即可。单次使用 `--out outputs/check`。多段日志默认按字节数选最大段，核对是否适合；必要时指定 `--index` 并裁掉起降/撞击片段。

## 解释证据

- 检查时间单位、采样率、断段、字段和解码错误。未记录数据视为未知。
- 比较连续窗口内频谱与对应油门、杆量，不拼接不相邻片段做 FFT。
- D-term 单位与增益有关，不能把固定 RMS 阈值当成普适标准。
- RPM 开启配置不等于遥测无错；检查日志覆盖、频谱和实际 DShot 错误。
- 机体 Z 加速度不等于地面坐标垂直运动。推油门抖动应定位时域事件，并区分姿态抖、推力变化、油门输入和机械振动。
- 跟随误差与反卷积响应不能单独决定 P/I/FF/D；本工具不自动报告“过冲百分比证明 D 有效”。需要时用 PIDtoolbox、Blackbox Explorer 独立核查动作。

## 候选与交付

把每项候选写成 `changes.json`：`key`、`value`、`reason`、`evidence`（analysis.json 里的实际路径）。不把未知值补成默认值。

```sh
fpv-tune plan --analysis outputs/build/check-1/analysis.json --config dump.txt --profile 0 --changes changes.json --out outputs/plan
```

CLI profile 从 0 开始。检查配置与日志是否一致，多个 profile 要明确选择。可执行计划目前限定 Betaflight 4.5.2 的已支持参数；其他版本做分析并列出兼容性缺口。

手动调 PID/LPF 时，计划会关闭对应的简化模式并写明原因，不同时改手动数值与简化倍率。输出完整审查表、差异 CLI、完整已知配置、回滚 CLI；用户明确要保存命令时可用 `--include-save`。

候选参数未经过新的实飞验证，报告要据实标注；脚本不连接飞控或写串口。默认不上传原始日志、机体标识、GPS、配置快照或个人路径。
