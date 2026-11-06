# 穿越机自动调参技能

[English](README.en.md)

## 安装

下载项目后，在项目目录运行：

```sh
python -m pip install ".[plots]"
python tools/install_skills.py
```

已经装过依赖，更新技能只需运行：

```sh
python tools/install_skills.py --update
```

需要 Python 3.10 或更新版本。

## 使用

在 Codex 中调用 `$穿越机调参`，附上黑盒文件和当前配置，说明机型及飞行时的问题。例如：

```text
用 $穿越机调参 分析这份黑盒，PID 和滤波一起调。
推油门时有小幅抖动，锁定感不够。
```

调参按三次飞行进行：

1. 发第一次飞行的黑盒，得到初调参数。
2. 应用参数后再飞，发新黑盒，继续修正。
3. 再飞一次，检查抖动、跟随和电机温度，确认需要保留或回退的设置。

每次都会检查 PID、D-min、FF、两级低通、RPM 滤波、陷波和油门相关设置，并给出完整参数、修改命令及回滚命令。有问题可以继续复调。

## 文件与版本

- 黑盒：`.bbl`、`.bfl` 或已解码的 CSV。
- 当前配置：Betaflight 导出的 `dump` 或 `diff all`。
- 原始黑盒需要 `blackbox_decode`，可使用 PIDtoolbox 安装目录里的解码器。
- 参数命令目前按 Betaflight 4.5.2 核对；其他固件先分析，再确认参数兼容性。
- CLI 的 `profile 0` 对应界面里的“PID 配置文件 1”。

参数通过 Betaflight CLI 应用，原始飞行日志保留在本地。

[命令行用法](docs/usage.md) · [复飞流程](docs/workflow.md) · [参考资料](docs/research.md) · [下载](https://github.com/hnnjmhv/fpv-tuning-skills/releases)
