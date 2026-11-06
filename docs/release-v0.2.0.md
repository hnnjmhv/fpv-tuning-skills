# v0.2.0 · 穿越机调参 / FPV Tuning Skills

## 中文

- 中英文技能入口与中英文分析报告，共用同一个 Python 引擎。
- 默认三次真实飞行检测：基线联合调参、第二次复查修正、第三次验收与剩余问题。
- 每次同时审查 PID、动态 D、FF、gyro/D-term 两级低通、RPM、陷波、TPA、Anti-gravity 和油门表现。
- 输出完整已知配置、差异 CLI、回滚 CLI，并标记缺失数据与未验证候选。
- 补齐连续时间窗、物理单位、配置 profile、版本枚举、日志去重与简化控制一致性检查。
- 中英文研究资料包含 66 项一手引用，并明确修正旧流程中过度推断的结论。
- 本地 57 项测试通过；Windows/Linux、Python 3.10/3.13 跨平台 CI。

可执行参数计划目前支持 Betaflight 4.5.2 的已核对参数子集。其他版本可分析数据，但需要对应版本适配后才能生成可执行配置。软件测试不代表实飞机体验收。

安装步骤见仓库 README。下载源码包或克隆仓库后，在虚拟环境执行 `python -m pip install ".[plots]"` 和 `python tools/install_skills.py`；更新本机同名技能加 `--update`。

## English

- Chinese/English skill entrypoints and reports share one Python engine.
- Three actual flight checks by default: joint baseline proposal, flight recheck/revision, and evaluation with remaining issues.
- Every check covers PID, dynamic D, FF, both gyro/D-term low-passes, RPM, notches, TPA, Anti-gravity and throttle behavior.
- Full-known, differential and rollback CLI outputs distinguish missing data from unvalidated proposals.
- Continuous-window measurements, physical units, profile identity, versioned enums, duplicate-log checks and simplified-control consistency replace unsupported automatic rules.
- Bilingual research includes 66 primary references and corrects overstated claims from the prototype.
- 57 local tests; Windows/Linux CI on Python 3.10/3.13.

Executable plans currently support a verified Betaflight 4.5.2 subset. Other firmware remains analysis-only pending a version adapter. Software tests are not real-airframe flight acceptance.

See the README for installation. From a cloned repository or extracted source archive, install `".[plots]"` in a virtual environment, then run `python tools/install_skills.py`; add `--update` for an existing installation.
