# 命令行用法

在已安装项目依赖的 Python 环境中运行 `fpv-tune`。

## 分析黑盒

```sh
fpv-tune inspect --log flight-1.bbl
fpv-tune start --session outputs/my-build --checks 3
fpv-tune analyze --log flight-1.bbl --decoder /path/to/blackbox_decode --session outputs/my-build --plots
```

`inspect` 列出文件内的飞行段。默认选择字节数最大的一段，用 `--index N` 可以指定。排除起降或碰撞片段时，加 `--start-s` 和 `--end-s`，时间相对该段日志开始计算。

第二、三次飞行对同一会话运行 `analyze`，换成新的黑盒文件即可。用 `--metadata context.json` 记录桨、电池、机型和飞行模式，用 `--symptom` 记录本次问题。

只分析一次时，把 `--session` 改为 `--out outputs/check`。

## 分析 CSV

```sh
fpv-tune analyze --csv flight.csv --config dump.txt --profile 0 --out outputs/check --plots
```

时间列应标注 `(us)`、`(ms)` 或 `(s)`，也可以指定 `--time-unit`。gyro 和 setpoint 应标注 `(deg/s)`；`(rad/s)` 会换算。没有 setpoint 单位时，只对已确认的 Betaflight 4.5 非高分辨率日志推断单位。

多 profile 配置需要用 `--profile` 选择。CLI 的 profile 从 0 开始。

## 生成参数命令

技能根据日志填写 `changes.json`，每项写明参数名、建议值、原因及对应的分析指标路径：

```json
{
  "changes": [
    {
      "key": "p_pitch",
      "value": 42,
      "reason": "格式示例，请替换为本次分析得到的理由。",
      "evidence": ["axes.pitch.tracking.normalized_mae"]
    }
  ]
}
```

示例中的 42 不代表任何机型的推荐值。

```sh
fpv-tune plan --analysis outputs/my-build/check-1/analysis.json --config dump.txt --profile 0 --changes changes.json --out outputs/my-plan
```

输出文件：

- `candidate-cli.txt`：本次修改。
- `full-reviewed-cli.txt`：完整的已知参数。
- `rollback-cli.txt`：恢复修改前的参数。
- `plan.json`：修改理由和指标记录。

需要末尾带 `save` 时，加 `--include-save`。没有记录或尚不支持的参数会在说明中列出，不会补成默认值。手动修改 PID 或低通时，对应的简化模式会关闭，避免滑块重新计算覆盖数值。

## 查看结果

每次检测的目录包含 `analysis.json`、报告、参数表和可选频谱图。第二次会与第一次比较；第三次还会对照初始基线，并输出 `validation.json` 供记录实际飞行结果。

相同黑盒不能重复计为新一次飞行。检测次数完成后仍有问题，可以另建会话继续调。
