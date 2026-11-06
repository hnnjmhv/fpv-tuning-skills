# 穿越机自动调参技能 v0.2.0

- PID 和滤波一起分析，给出完整参数、修改命令和回滚命令。
- 按三次飞行调参：初调、复查修正、确认效果。
- 支持 `.bbl`、`.bfl` 和已解码的 CSV。
- 参数命令目前支持 Betaflight 4.5.2。

下载源码包后，按 [安装说明](https://github.com/hnnjmhv/fpv-tuning-skills#安装)操作。已经装过依赖，更新时运行 `python tools/install_skills.py --update`。

## FPV Auto Tuning Skill v0.2.0

- Adjust PID and filters together, with full settings, changed commands and rollback commands.
- Three flights: initial tune, revision, and a final check.
- Reads `.bbl`, `.bfl` and decoded CSV.
- Configuration commands currently support Betaflight 4.5.2.

Download the source archive and follow the [installation instructions](https://github.com/hnnjmhv/fpv-tuning-skills/blob/main/README.en.md#install). If the dependencies are already installed, run `python tools/install_skills.py --update`.
