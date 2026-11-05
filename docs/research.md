# FPV Betaflight 黑盒调参研究与声明审计

检索与本机核对日期: **2026-11-05**。英文对应文件: `research.en.md`。两份文件的结论、证据编号和限制相同。

## 1. 范围与证据规则

- **固件事实**: 下文以 Betaflight **4.5.2** 标签对应提交 `024f8e13d4e642eb6a380308685b9ea3aa3ef1a2` 为主要基线，不把整个 4.x 系列视为同一实现。[V45]、[T45]
- **当前差异**: 检索时官方 latest 稳定发行版为 **2026.6.2**, 发布时间为 2026-09-16; 对照提交为 `e0b7bb01b17b21351057e9ead2d1ab39dd44fa16`。这里的“当前”仅指这个检索快照，不代表 master、预发行版或以后版本。[V26]、[T26]
- **来源优先级**: 实际飞控版本及完整配置 > 对应标签源码 > 对应版本发行说明 > 持续更新的官方 Wiki。源码中的 C 结构成员、CLI 名称、GUI 标签和 Blackbox 头字段不能互当别名。
- **工程决策**: 数据分段、谱估计、质量门控、对比统计及下述三次实飞流程，是技能仓库的离线 DSP/实验设计决策，不是 Betaflight 官方规定的调参程序。SciPy/MathWorks 文档证明算法定义，不证明某组飞控参数安全或最优。
- 本资料研究环节没有解码用户飞行日志、没有连接或改写飞控、没有实飞，也没有验收新软件；主项目的软件回归另行记录。文中不提供通用 PID、截止频率、TPA、FF 或相干性阈值预设。

## 2. 应保留、改写或拒绝的声明

| 待审声明 | 审计结论及可发布措辞 |
| --- | --- |
| “必须打开 GYRO_SCALED 才能看原始陀螺” | 改写。4.5 已加入默认未滤波陀螺日志; 必须检查具体日志是否含 `gyroUnfilt`。旧分析器可能仍依赖该 debug，但这是兼容性要求，不是固件必需条件。[W45]、[B1]、[B3] |
| “gyroUnfilt 是传感器全速、无任何处理的 ADC” | 拒绝。它来自校准、对齐、缩放后的陀螺变量，并被日志抽取; 不代表未受硬件滤波影响的全速连续观测。[B2]、[G1]、[G3] |
| “开启双向 DShot/RPM 选项就证明 RPM 滤波有效” | 拒绝。配置、逐电机有效遥测、实际 notch 生效及频谱结果是不同证据层级。[R1]、[R2]、[R3] |
| “看到 RPM_FILTER debug 就证明滤波器已启用” | 拒绝。4.5.2 在检查滤波器是否启用之前就填写该 debug。[R1] |
| “LPF2 只是多余延迟，有 RPM 就应关闭” | 拒绝。Gyro LPF2 位于 gyro 到 PID 降采样前; RPM notch 位于其后。是否可减弱要结合采样关系、混叠风险和实际噪声判断。[G2]、[G3] |
| “4.5.2 的 d_roll 是平稳飞行基值” | 拒绝。该版本 CLI 的 `d_roll` 是动态 D 的上限，`d_min_roll` 才是启用动态 D 时的基值。[P1]、[P2] |
| “Anti-Gravity 只增加 I / 提供抗重力升力” | 拒绝。4.5.2 按油门变化触发 roll/pitch 的 I 积分加速和 P 增强，不是高度或垂直推力控制器。[A1]、[A2]、[A3]、[P3] |
| “FF、feedforward_boost、throttle_boost 都是一种 boost” | 拒绝。前两者作用于角速度指令前馈路径; 后者是混控油门的瞬态高通增强。[F1]、[F2]、[M1] |
| “一次回弹就能确定是 P、D、FF 或 AG 的某个错误” | 拒绝单因果归因。还需检查指令、I-term relax、遥测、执行器余量、模式和动作条件。[P2]、[P3]、[F1] |
| “body Z 加速度下降就是地面系垂直抖动改善” | 拒绝。机体系 Z 不是地面垂直; 姿态、重力参考、平动及旋转效应都可能改变它。[ACC1]、[ACC2] |
| “相干性超过某一固定值即可自动调 PID” | 拒绝。相干性是依赖频率、激励和估计条件的质量证据，没有从这些来源获得适用于所有飞行的阈值。[D2]、[D3]、[D5] |
| “把反卷积阶跃尾部归一到 1 就证明无稳态误差” | 拒绝。该处理可能强行制造单位增益，隐藏低频不可辨识、截断和正则化偏差。须保留未归一结果及独立参考，见第 7 节。 |
| “前后两次自由飞行分数变好就证明参数导致改善” | 拒绝。未匹配动作和工况只能报告关联; 同时改变 PID 与滤波时，更不能把变化归给某一个参数。 |
| “新离线脚本等同于 PIDtoolbox” | 不支持。原作者 `PTstepcalc.m` 本次不可访问; 通用 DSP 能力、相似图形或第三方移植不构成算法与数值等价证据。[PT1]、[PT2] |

## 3. Blackbox 字段、类型、单位与采样契约

### 3.1 必须读取实际头部

每个文件内每个 log index 都应单独读取 `Firmware revision`、板卡/构建信息、`Field I name/signed/predictor/encoding`、`I interval`、`P interval`、`looptime`、`pid_process_denom`、`gyro_scale`、`acc_1G`、`motorOutput`、`blackbox_high_resolution`、debug 模式和字段开关。字段可因编译选项、传感器不存在、D 值为零或字段禁用而缺失。缺失不等于测量值为零。[B1]、[B3]、[B4]

以下“整数”指日志协议的有/无符号值，不是固定 CSV 列类型。固件采集缓冲对 gyro、setpoint、acc、debug 使用 `int16_t`，对 PID 分量使用 `int32_t`; 编码仍按头部定义。`lrintf` 表明浮点控制量在记录前已量化。差分编码的 `AVERAGE_2` 是预测器，不是对真实信号额外做两点平均。[B1]、[B2]、[B5]

### 3.2 4.5.2 主要分析字段

定义 `h = 10` 当 `blackbox_high_resolution` 开启，否则 `h = 1`。以下换算针对**尚未做物理单位换算的已解码字段值**; CSV/GUI 若已换算，不能再除一次。[B2]、[B6]、[E1]

| 字段 | 类型及物理含义 | 分析约束 |
| --- | --- | --- |
| `time`, `loopIteration` | 无符号整数; 原始时间为微秒，迭代数为 PID 循环索引 | 检查单调性、回绕、复位、丢帧和重复; 不由 CSV 行号推时间。[B1]、[B2] |
| `gyroADC[0..2]` | 有符号整数; 软件滤波后的 roll/pitch/yaw 角速度，原始值除以 `h` 为 deg/s | 这是正常 rate PID 测量量，不是姿态角，也不是原始 ADC。[B2]、[P3] |
| `gyroUnfilt[0..2]` | 有符号整数; 对齐/缩放后、软件滤波前的角速度，原始值除以 `h` 为 deg/s | 日志保存的是所取时刻的值，不保证捕获所有 gyro 样本。[B2]、[G1] |
| `setpoint[0..2]` | 有符号整数; PID 采用的角速度目标，原始值除以 `h` 为 deg/s | 比较跟踪时优先于重新从摇杆和 rate 曲线推算; 不等于原始接收机输入。[B2]、[P2] |
| `setpoint[3]` | 有符号整数; `mixerGetThrottle()` 乘以 1000 | 除以 1000 为该日志油门变量，除以 10 为百分比; **不受 `h` 缩放**。含油门限制和 throttle boost，不含后续 thrust-linearization 补偿、dynamic idle 或 airmode。[B2]、[M1] |
| `rcCommand[0..3]` | 前三列有符号、油门列无符号编码; 是处理后的控制输入 | 不是四列 deg/s。高分辨率影响四列; GUI 对前三列再加中心偏移显示微秒，不应拿显示值当 PID setpoint。[B1]、[B2]、[E1] |
| `axisP/I/D/F[axis]` | 有符号整数; 对应控制器各项输出，按固件控制量单位记录 | 不是 GUI 的 P/I/D/F 增益，不是 deg/s 或力矩 SI 单位; `axisD` 已含动态 D 和 TPA。[B2]、[P2] |
| `motor[n]` | 无符号日志编码; 发给电机输出路径的指令 | 按 `motorOutput`、协议与 mixer 解释; 不能固定假定 1000..2000，也不是 RPM 或实际推力。触顶只支持指令余量分析。[B1]、[B2]、[B4] |
| `eRPM[n]` | 无符号日志编码; **电气 RPM / 100** | 若磁极数为 `p`, 则机械 RPM = `raw * 100 / (p/2)`，机械转频 Hz 再除以 60。先确认导出器是否已转换，以及极数是否真实。[B1]、[R2]、[E1] |
| `accSmooth[0..2]` | 有符号整数; 对齐、校准、可选低通后的机体系加速度传感器数据 | 原始值 / `acc_1G` 为 g; 不是去重力的地面系加速度。列名不保证一定开启了低通。[B2]、[B4]、[ACC1] |
| `debug[0..7]` | 有符号整数; 模式相关的内部量 | 通道数量、轴、采样位置、缩放逐版本查源码; 不能统一套用 `h` 或给所有 debug 标 deg/s。[B1]、[G3]、[P2] |
| `vbatLatest`, `amperageLatest` | 电压为无符号整数，电流为有符号整数; 4.5.2 的通常原始标度分别为 0.01 V、0.01 A | 校准和传感器来源仍需验证; 导出器可能已转换为 V/A，不可重复换算。[B2]、[U1] |

`eRPM`、加速度等字段即使随主帧重复写入，也不代表传感器或 ESC 在每个日志时刻都给了新样本。尤其 4.5.2 无效 DShot 包不会更新有效值，因此连续相同值既可能是稳定转速，也可能是重复/陈旧遥测，不能只靠非零判断健康。[R3]、[ACC1]

当前 2026.6.2 保留 gyro/setpoint 的高分辨率规则、`setpoint[3]` 的千分比和 eRPM 的电气 RPM/100 标度，但还可有条件记录翼机 `axisS`、更一般的 servo 通道和 `imuQuaternion[0..2]`。后者是选择 w 为正号后、乘以 32767 记录的 x/y/z 分量，不是三路姿态角; 不应把新字段按 4.5.2 的固定列号读取。有姿态四元数也仍须核对坐标约定、同步和估计有效性，不能自动把 accSmooth 当作地面系线加速度。[B26]、[B26F]、[R26]

### 3.3 抽取与混叠

4.5.2 的常规日志抽取间隔为 `N = 2^sample_rate` 个 PID 循环。名义日志率约为 `f_PID / N`，而不是固定 1 kHz/2 kHz; `f_PID` 又取决于 gyro 采样及 PID 分频。I 帧另有调度，极低记录率可只写 I 帧。最终应由实际 `time` 差分、`loopIteration`、头部和解码器缺帧统计交叉核对。[B4]、[B6]、[B7]

工程要求: 报告有效采样率、间隔分布、缺口位置、连续段时长和可分析频带。日志抽取不是自动抗混叠滤波; 尤其 `gyroUnfilt`/`GYRO_SCALED` 的高频可能折叠到日志 Nyquist 以下。不能通过插值、补零或提高 FFT 点数恢复已丢失的带宽。[B2]、[G3]、[D1]、[D4]

`blackbox_decode --raw` 表示不应用预测器重建、输出字段差分，**不是“导出未滤波陀螺”**。导出须记录解码器版本、完整命令及单位选项; 使用普通重建模式，保留原始 BBL/BFL/TXT 和解码错误统计。[U2]

## 4. RPM 与滤波的证据链

### 4.1 RPM: 不能从设置推断测量

4.5.2 的 RPM 滤波初始化要求双向 DShot 可用且谐波数量非零; 权重为零的谐波不产生滤波作用。Blackbox 的 `eRPM` 字段存在条件则是电机数量、双向遥测开关和 RPM 字段开关，并不检查每个采样是否新鲜有效。`RPM_FILTER` debug 在 `isRpmFilterEnabled()` 返回前就被填写，因此它本身也不是启用证明。[R1]、[B3]

应分开记录四层证据:

1. 配置与能力: 电机协议、双向 DShot、ESC 固件支持、实测磁极数、谐波/权重/Q/最低频率/遥测 LPF 和编译特性。
2. 实际遥测: 逐电机速度、随动作变化、零值/平台/异常跳变、包错误统计; 在安全地面检查时拆桨。官方提供 `dshot_telemetry_info` 以查看逐 ESC 包成功情况，但本次没有连接执行。[WDEBUG]、[WRPM]
3. 滤波路径: 本版本实际启用，notch 频率及权重合理，并确认待分析通道处于滤波前还是后。[R1]、[G3]
4. 飞行结果: 在匹配转速/工况的频谱中观察电机谐波残余、D 噪声与电机温度等; “已配置”与“效果已验证”分别报告。

标签源码还明确显示: 双向 DShot 开启但未得到所需逐电机遥测时，4.5.2 会设置 `ARMING_DISABLED_DSHOT_TELEM`。不要用旧指南的 `RPMFILTER` 字样猜测所有版本的具体报错，更不要通过绕过解锁保护来完成调参。[ARM45]

RPM 谐波跟踪针对电机相关频率，不代表所有结构共振、桨损伤、轴承问题和宽带噪声都会被去掉。先检查机械状态，不用减滤波掩盖未知硬件问题。这是诊断边界，不是某个 notch 数量的通用建议。

### 4.2 Gyro LPF2 的抗混叠位置

4.5.2 在 gyro **采样率**初始化并运行 Gyro LPF2，然后降到 PID 速率; 若 LPF2 不启用，使用简单平均。之后才有 RPM 滤波、静态 notch、Gyro LPF1 和动态 notch。当前 2026.6.2 仍保留 LPF2/平均这条降采样路径。[G1]、[G2]、[G3]、[G26]

因此“LPF2 在 PID 降采样前承担抗混叠角色”是从实际路径得到的工程解释; 它不是任意截止频率都足够的保证。后置 RPM/notch 不能撤销已经混叠的分量。也不要混淆传感器内部硬件 LPF、Gyro LPF2、D-term LPF2 和离线重采样 FIR。

只有获得采样关系、滤波器类型/阶数、前后谱、D 噪声、CPU/丢帧和电机热状态，才讨论减少滤波的具体变更。4.5.2 的普通 `gyroADC` 不能单独说明某一层滤波的衰减或延迟; `GYRO_SAMPLE` debug 提供不同阶段观测，但同样受日志率限制。[G3]

## 5. PID、动态 D 与简化滑块的版本语义

### 5.1 角速度环而非垂直加速度环

在正常 Acro rate 路径，P 取角速度误差，I 积分其经 relax 等处理后的误差，D 来自额外滤波后 gyro 的负导数，F 来自指令前馈路径。Angle/Horizon、launch control、crash recovery、yaw-spin 和控制限幅会改变这些关系。不能从“掉高度”或某个 body-Z 峰值直接反算 P/I/D。[P2]、[P3]

### 5.2 动态 D 映射

| 项目 | 4.5.2 | 当前 2026.6.2 |
| --- | --- | --- |
| 基值与上限 | 动态 D 生效时，`d_min_roll/pitch/yaw` 是基值，`d_roll/pitch/yaw` 是上限 | `d_roll/pitch/yaw` 是基值，`d_max_roll/pitch/yaw` 是上限 |
| 启用条件 | 基值大于零且小于主 D; 否则使用固定主 D，而非把 D 关闭 | 主 D 大于零且 d_max 大于主 D 才有动态提高 |
| 敏感度 CLI | **已经是** `d_max_gain` 与 `d_max_advance`; C 成员仍叫 `d_min_gain`/`d_min_advance` | CLI 仍为 `d_max_gain` 与 `d_max_advance` |
| 内部计算 | setpoint 通道敏感度包含 gain 与 advance 的乘积 | gyro gain 与 setpoint advance 分别控制两条通道，不能按旧乘积解释 |
| 简化动态 D CLI | `simplified_dmax_gain`，映射内部 `simplified_dmin_ratio` | `simplified_d_max_gain` |
| Debug | `D_MIN`: [2]/[3] 分别为 roll/pitch 的活动 D 增益乘以 10，且仅动态路径填写 | `D_MAX`: 针对 `gyro_debug_axis`; [2] 为该轴活动 D 增益乘以 10，[3] 为增益倍率乘以 100 |

上述比较来自固定版本初始化、计算和 CLI 映射，不是把 Wiki 历史表机械套入 4.5.2。[P1]、[P2]、[N45]、[C45]、[P26]、[I26]、[N26]、[S26]

重要限制: 当前官方 Dynamic D 页面仍把早期迁移写作 `d_min_boost_gain -> d_max_gain`，且把 D_MAX [2]/[3] 描述为 roll/pitch; 这不能替代上表对应标签源码。其默认值也不能视为所有版本/构建的实测配置。精确更名时间和所有中间版本没有在本次穷举。[WD]

`D_LPF` 在 4.5.2 的 [0]/[1] 来自**已过 gyro 滤波、未过 D 专属滤波**的负角速度导数，并除以 25; 它们不是原始 ADC，也不是已乘 D 增益的输出。[2]/[3] 为动态 D 作用后、TPA 前的 D 输出并乘以 10。普通 `axisD` 则在 TPA 后。不能只给这些通道套同一种单位或标度后直接比较。[P2]、[DL45]、[DLS45]

### 5.3 简化模式和滑块不是独立参数

`OFF` 不通过简化 PID 滑块重算; `RP` 控制 roll/pitch，`RPY` 包括 yaw。Gyro/D-term 的简化滤波开关与 PID 模式分别存在; 关闭 PID 简化不等于关闭全部滤波滑块。切换模式、重新应用滑块可能重写轴增益，应保存变更前后实际 CLI 值。[S45]、[C45]、[WPID]

4.5.2 滑块基于**固件默认增益**重算，不是对任意现有手工值做相对加减: master 影响 P/I/D/F，PI 影响 P/I，I 滑块进一步影响 I，D 影响基值和上限，动态 D 滑块改变基值到上限的差距，pitch PI 还影响 pitch F。滤波 multiplier 放大已启用 LPF 的截止频率; 更大通常是更少滤波，不是“更多滤波”; 已关闭路径不会因此自动全部开启。[S45]

当前动态 D 公式及 CLI 名称有变化，不能只复制滑块数值后承诺相同控制器。报告至少同时列出模式、滑块、最终原始增益、滤波类型/频率和版本。[S26]、[N26]

## 6. Anti-Gravity、FF、TPA 与油门瞬态

### 6.1 Anti-Gravity

4.5.2 以油门变化的绝对导数为输入，按油门位置和增减方向加权，再作 PT2 平滑; `anti_gravity_cutoff_hz` 会影响峰值与持续过程。启用后，`anti_gravity_gain` 驱动 roll/pitch 的 I 积分加速; `anti_gravity_p_gain` 参与额外 P 增强，P 增强在较大角速度目标时衰减。yaw 不接受这两种 AG 增强。[A1]、[A2]、[A3]、[P3]

因此 AG 不仅影响 I，也不是基于高度、body Z 或“重力大小”的反馈。油门切换时的姿态误差只能支持把 AG 列为候选，还需检查重心、推力余量、电压、I-term relax、混控和滤波。当前 2026.6.2 仍采用该油门导数输入机制; 不据此承诺所有瞬态响应或默认值完全相同。[A26]

4.5.2 `ANTI_GRAVITY` debug [0]/[1] 是不同处理阶段的导数量乘以 100，[2] 是相对 pitch Ki 的 I 增强比乘以 1000，[3] 是 pitch P 增强比乘以 1000; 它们不是四路加速度，且不能照抄持续更新的 debug 简介。[A1]、[A2]、[A3]

### 6.2 Feedforward

4.5.2 的 FF 使用 rate 曲线后的目标变化及 RX 时间信息，包含重复包处理、平滑、加速度 boost、中心 transition、averaging、jitter reduction 和接近最大 rate 时的限制; 有 RC smoothing 时还对 FF 作 PT3 滤波。最终 F 输出又乘轴 F 系数。仅用 `setpoint` 的离线有限差分通常不能逐样本复现该路径。[F1]、[F2]、[P2]

`feedforward_boost` 增加指令变化的加速度分量; `feedforward_max_rate_limit` 在 4.5.2 按剩余最大 rate 余量限制同方向 FF，并非简单的“到某个摇杆百分比开关”。FF 噪声、起步超调和停止回弹需连同 RX 实际包率、量化、RC smoothing 和执行器限制判断。[F1]

官方 Feed Forward 2.0 页面开头明确讨论 4.1，其旧参数名和“FF 不会造成振荡”的绝对表达不能作为 4.5.2/当前版本的通用因果规则。理想前馈不直接修改反馈极点，不代表 RC 噪声、激励共振、饱和或人机闭环不会产生抖动。这一句是工程解释，不是官方安全保证。[WFF]、[F1]

当前 2026.6.2 的 FF 已重构; roll/pitch 的 boost 与 yaw 路径分开，yaw 包含 hold 分量。不能把 4.5.2 的 yaw FF 特征和 debug 缩放直接带过去。[F26]

### 6.3 TPA

在 4.5.2 的正常编译路径，`tpa_mode=D` 仅衰减 D，`PD` 同时衰减 P/D，而不是把所有 PID/FF 同比缩小。没有 `USE_TPA_MODE` 的构建存在不同 P 路径，故仍须确认构建能力。低油门 TPA 另有 breakpoint、rate 和是否持续启用的逻辑; 不应把高油门公式套遍全程。[P4]、[P5]、[P1]

在只讨论经典高油门分支、归一化油门为 `t`、归一化断点为 `b` 时，倍率可表示为 `1 - (tpa_rate/100) * max(t-b,0)/(1-b)`，实际初始化还对断点作限制。增大正的 tpa_rate 是加大衰减，不是增加高油门 D 阻尼。当前版本新增翼机相关 TPA 路径，不应把 `PDS` 或速度 TPA 当作 4.5.2 四轴通用能力。[P1]、[P4]、[TPA26]

### 6.4 Throttle boost 及输入位置

4.5.2 先在限制后的油门上更新 AG、TPA 和动态 LPF，再将油门高通分量乘 `throttle_boost` 加回并限幅。它不是 FF boost，也不是提高 P/I/D; 在加油和收油时都会改变瞬态混控输入。`throttle_boost_cutoff` 控制该高通构造中的低通。[M1]

因此 `setpoint[3]` 含 boost，而计算 TPA/AG 的油门位于 boost 前; **不能只把 setpoint[3] 代入 TPA 公式，就声称重建了实际 TPA**。dynamic idle、airmode、thrust linearization、throttle limit、RPM limiter、电池与电机输出限制也都应作为对比协变量记录。[M1]

## 7. 推断前提与离线 DSP 决策

本节是仓库方法约束，不是 Betaflight 官方调参预设。

### 7.1 跟踪误差与加速度各自能说明什么

同轴 `setpoint - gyroADC` 在单位、时间和模式已核对时，是控制器所见的 rate 跟踪误差。报告有效激励范围、按动作/油门分层的误差、超调与恢复过程; 没有动作的平稳段误差小，不证明动态跟踪好。大误差也可能来自饱和、受限目标、模式转换或外扰，不唯一指向增益偏低。[P2]、[P3]

`accSmooth` 是机体系测量，姿态变化会改变重力参考在各轴的投影，传感器离旋转中心的距离还会引入旋转相关分量。没有可靠姿态、坐标系、时间同步、重力处理和传感器位置信息，不能把 body Z 当作地面垂直，不能从它确定高度保持性能或唯一归因到 pitch PID。仅凭加速度计算倾角在动态飞行也不成立。[ACC1]、[ACC2]

### 7.2 直接阶跃与频域反卷积必须区分

直接 rate 阶跃分析需要可识别的指令基线、变化幅度、方向、保持段和足够恢复时间，且尽量在同轴、相似油门/电压/负载、无明显饱和或跨轴大动作条件下重复。有限上升沿不是理想瞬时阶跃; 停止/反转与起步分开分析。可按**实际指令变化量**归一化，并报告每个事件、样本数和离散度，不按输出尾部强制归一。

用 `r=setpoint`, `y=gyroADC` 做谱估计，得到的是该工况下的**指令到已滤波角速度的近似闭环关系**，包含前馈、反馈、滤波和限幅的影响; 不是裸机体 plant，也不是只由 P/D 决定的统一阶跃响应。H1 等估计依赖局部线性/近似平稳、足够激励及噪声相关性假设; 闭环反馈和飞手纠正会使某些辨识假设失效。[P2]、[P3]、[D5]

SciPy `csd(r,y)` 采用 `conj(FFT(r))*FFT(y)` 约定，故相容的 H1 形式为 `csd(r,y)/welch(r)`; 必须固定窗口、分段、overlap、去均值/趋势和物理单位。交换共轭方向会改变相位。低输入功率处不能直接除法; 正则化、频带选择及插值均需公开并做敏感性检查。[D1]、[D3]、[D5]

反卷积/FRF 经 IFFT、积分得到的“估计阶跃”还受频带截断、DC 缺失、窗函数、因果对齐、边界和正则化影响。强制其尾部等于 1 会掩盖增益误差或不可辨识的低频。若为了展示做归一化，必须同时给未归一结果、比例因子、尾窗、DC/稳态证据和敏感性结果; 低频不足时标记“稳态增益不可辨识”，不得用归一后超调去推荐 PID。

相干性 `abs(Pxy)^2/(Pxx*Pyy)` 只描述在所用估计条件下的频率相关性。门控须结合输入功率、有效独立平均数、置信/重复性及目标频带; 极少分段甚至会产生虚高相干性。**没有通用通过阈值**。若做 coherence gating，应发布规则、被屏蔽频带和对结果的影响; 把低相干频点直接清零再 IFFT 也会改变时域形状，不能把变平滑当改进。[D2]、[D3]

### 7.3 谱与时间处理

- 先按复位、解锁区间、模式和大缺口分段，不跨缺口拼连续 FFT; 不为让算法运行而用长线性插值隐藏丢帧。
- 需要统一采样率时先验证各连续段的时间轴; 合理的降采样应有抗混叠滤波。`resample_poly` 的 FIR/边界假设是离线处理选择，不能逆转记录前的混叠。[D4]
- 同一物理量的 Welch PSD 应以该量平方/Hz 表示，例如 `(deg/s)^2/Hz`; 幅谱、功率谱和 PSD 不能混用。比较须使用相同频带、窗口秒数、标度和色阶; 不能把一般数字信号 PSD 无依据称为 dBm/Hz。[D1]
- 先分离指令动作、撞击/着陆、propwash 与相对稳定的噪声段，再按 RPM/油门分层比较。D 谱还受导数、增益、动态 D 和 TPA 影响，不能只用总 RMS 推导“滤波够了”。[P2]
- 零相位前后向滤波可以用于明确标注的离线显示/分析，但其相位特性不是飞控实时因果滤波的延迟，不能据此证明新滤波“无延迟”。[D6]

## 8. 默认三次实际飞行检查与多日志处理

**三次实飞是项目默认工作流，不是官方保证，也不是三个软件分析次数。** 不强制把 PID 和滤波拆成独立轮次。每轮均审查两者; 保持不动也应明确写出理由。

| 实飞检查 | 输入与动作 | 必须交付 |
| --- | --- | --- |
| 第一次: 基线 | 机械/遥测/日志质量合格后，使用已确认可安全飞行的原配置; 采集可复现 rate 动作、油门变化和实际用途片段 | 完整基线诊断与**联合 PID+滤波方案**: 每轴 P/I/D/动态 D/FF、AG、TPA、throttle boost、gyro/D-term/RPM/动态 notch 均标记建议修改或保留、证据、风险、复飞验证点。缺证据时保留，不编造数值。 |
| 第二次: 比较与修订 | 核实实际应用的整套变更，重复尽量匹配的动作、方向和工况，记录电池、风、负载和温度 | 对基线与新日志按可比片段比较; 识别改善、退化和不可比部分，给出联合 PID+滤波修订及保留项。多项同时变化时只评价整套方案，不虚构单参数因果。 |
| 第三次: 验证与剩余问题 | 使用第二次修订，重复验证动作并覆盖目标用途; 保留独立事件用于验证 | 逐项“通过 / 未通过 / 未覆盖”，列出剩余噪声、跟踪、遥测、热状态、饱和或不可辨识问题，以及有条件的下一步。不得用单次好看的曲线宣布全工况最优。 |

飞行由具备条件的操作者执行; 未排除的机械故障、异常电机热/声、遥测故障、明显失稳或不安全场地应先停止。三次不是必须冒险完成的配额; 数据不足或第三次未通过时如实列出待补证据，而不是保证三次收敛。把 PID 与滤波一并修改便于完整方案验证，但会降低单个参数的因果可分性，报告中要说明这个取舍。

### 多日志工程流程

1. 建立 manifest: 文件哈希、原路径、飞行序号、log index、时间、固件/板卡/构建、配置快照、实际变更集、解码器/分析器版本。一个 BBL 文件可能含多次解锁，文件数不等于飞行次数。[U2]
2. 每个 log 独立解码、核对字段与单位、时间质量、有效遥测和可用频带。版本/机体/桨/传感器路径不同的日志先分组，不盲目合并。
3. 每个连续段标注模式、动作、轴、方向、角速度幅度、油门/RPM、电压与饱和迹象; 保留被排除片段和排除原因。
4. 先给逐日志/逐事件结果，再在匹配工况中汇总; 统一谱处理参数并公开有效时长、事件数与覆盖。不能让长悬停日志吞没短但关键的动作，也不能跨日志边界反卷积。
5. 把“调参用事件”与“第三次验证事件”分开。重复窗口不是独立实飞样本; 只有少数实飞时，不报告虚假的统计精度。
6. 输出观察、候选解释、联合改动、验证结果和未知项。无匹配动作的 before/after 可以作探索性证据，不能给因果改善百分比; 即使三次看似更好，也不排除风、电压、飞手和顺序效应。

## 9. 实用数据接收清单

- 原始完整 BBL/BFL/TXT 及每个文件的 log index/解锁区间; 不只发截图、截断 CSV 或挑选的最好片段。
- `version`、`status`、`tasks`、完整 `dump all`/适当的配置导出、活动 PID/rate profile、构建特性和 Configurator/App 版本; 这些是待采集的只读证据，不是本次已经执行的飞控命令。
- 每次实飞前后的实际参数和变更集: PID/动态 D、FF/RC smoothing、AG、TPA 含低油门项、throttle boost/limit、gyro/D-term LPF、RPM/动态 notch、idle、airmode、mixer、thrust linearization 和输出限制。
- 飞控/gyro 型号及方向、gyro/PID/日志率、字段开关、高分辨率、debug 模式/轴、`motorOutput`、`acc_1G`、导出单位和丢帧统计。
- 电机型号/KV/真实磁极数、ESC 型号/固件/PWM 设置、双向协议支持、逐电机遥测与错误统计。配置截图不能代替实际遥测。
- 机架、桨尺寸/型号/桨况、整机和电池质量、负载/重心、安装软硬、螺丝/轴承/电机/机臂检查，及最近碰撞维修情况。
- RX 协议、实际包率、rate 曲线、RC smoothing 和链路异常; 缺失时 FF 解释需降级。
- 每轮电池规格/状态、电压段、环境风、飞手、动作顺序/标记、模式、同轴正反向动作、油门变化以及目标用途片段。
- 安全检查、电机温度的测量方式/时机、异常声、失步、饱和与飞行主观感受; 没有校准的触感不是精确温度。
- 如要讨论地面系线加速度或高度，额外要求姿态/坐标定义、传感器位置、同步及重力处理依据; 仅 accSmooth 不足。

## 10. 工具是否足够与 PTstepcalc 边界

### 已核对的本机事实

研究时提供的 PIDtoolbox 安装目录有 `PIDtoolbox.exe` 和 `blackbox_decode.exe`。仅运行后者 `--help`，其自报 **v0.4.6, Jun 10 2021 22:06:07**，SHA256 为 `D7379ED4EC0ABBB77A3461C9DD4A93AF440F243E0879CF197BF60739278565A0`。这只证明帮助入口可运行，不证明它正确支持 4.5.2 高分辨率、全部字段或 2026.6.2。资料研究未解码用户飞行日志，也未运行 PIDtoolbox GUI；主项目的后续本地回归与本资料核查分开记录。

官方 `blackbox-tools` 提供单位选项、log index、缺帧统计和 CSV 解码能力; 官方 Blackbox Explorer 源码包含高分辨率与机械 RPM 展示换算，可作为独立字段交叉核对参考。本次引用的源码快照分别为 `d89f96b983d0f5c8f053acf003ee2998b02b5b0f` 与 `e179902df4e38f24d4b61f114bf856a196c995be`，不代表上述本机 exe 就由这些提交构建。[U1]、[U2]、[E1]

### 能力充分性

| 任务 | 最低能力及本次结论 |
| --- | --- |
| 可追溯解码和单位核对 | 版本匹配的解码器、完整头部、错误统计、golden log/独立查看器交叉核对。现有 exe 的存在不等于兼容性通过。 |
| 噪声与跟踪诊断 | 可靠解码 + 时间/单位校验 + 成熟数组/DSP 库 + 分段/多日志报告，原则上足够做离线分析; 不必要求 PIDtoolbox GUI 自动化。[D1]、[D2]、[D3] |
| 新的阶跃/FRF 分析器 | 还需已知传递关系、纯延迟、低激励、丢帧、饱和、动态增益和多轴干扰测试; 图形相似不算验收。 |
| 安全参数与实际改进 | 还需完整机体/配置/遥测、温度与操作员的三次实际飞行证据; 离线工具不具备保证安全或自动确认改进的能力。 |
| PIDtoolbox 数值等价 | 证据不足，不能声称等价、替代实现或重现其当前算法。 |

### 原作者 PTstepcalc 可访问性

已尝试原作者仓库页面、GitHub API 和原始 `master/PTstepcalc.m` 链接; 本次均返回 404。作者网站可到达，但没有取得可用于核对的该算法源码。这不证明历史上没有源码，也不说明作者停止维护。[PT1]、[PT2]、[PT3]

因此本次**未审阅原始 PTstepcalc 实现，未移植、未复制其代码**。没有把第三方 fork/移植当作作者的一手算法或当前 PIDtoolbox。窗口、反卷积正则化、coherence gating、尾部归一化、统计筛选与版本差异均保留未知; 将来获得指定版本和授权可检查的源码、参考输出后，才另行作算法/数值对照。

## 11. 版本未知与发布验收

- 已完成的是 4.5.2 与 2026.6.2 的上述路径核对，不是所有中间发行版、板卡、云构建、ESC 和传感器的穷举验证。自定义构建必须以实际 `version`/配置及源码为准。
- 2026.6 官方说明列出 BIQUAD 到 SVF 的实现/选项变化和 thrust linearization 曲线重推导。它是升级风险提示，不是所有版本可直接搬同值的证明; 持续更新的发行说明还可能包含不属于已选标签的后续内容，具体差异仍需固定标签核查。[W26]
- 已知 Wiki 与固定源码在 CLI 名称、debug 布局等处存在冲突; 不把“官方站点当前页面”当作 4.5.2 完整规格。FF 2.0 页面属于历史语境，原 PIDtoolbox 方法仍不可访问。[WD]、[WFF]
- 新仓库发布前应以固定测试数据验证: 普通/高分辨率不重复缩放、机械 RPM 与极数换算、缺失字段不补零冒充观测、混合版本拒绝盲并、丢帧/时间回绕处理、已知延迟相位方向、弱激励与非单位 DC/尾部的拒绝或不确定性输出，以及两种语言的相同结论。
- 三次实飞报告必须把 PID 与滤波均纳入方案/比较/验证，并清楚标明没有做过的检查、未覆盖工况和单独参数因果不可辨识性。第三次不是“自动通过”。

## 12. 一手来源索引

代码链接固定到完整提交和相关行段; 官方在线指南是检索日快照，仍可能变化。DSP 文档固定到 SciPy 1.16.2，只用于算法定义，不要求项目安装该版本。PT 链接是可访问性核查记录，不是算法内容的引用。

- 版本: [V45]、[T45]、[V26]、[T26]。
- 4.5.2 日志/采样及当前字段: [B1]、[B2]、[B3]、[B4]、[B5]、[B6]、[B7]、[B26]、[B26F]。
- Gyro/RPM/加速度: [G1]、[G2]、[G3]、[G26]、[R1]、[R2]、[R3]、[R26]、[ARM45]、[ACC1]、[ACC2]。
- PID/滑块/CLI/油门: [P1]、[P2]、[P3]、[P4]、[P5]、[S45]、[C45]、[N45]、[M1]、[A1]、[A2]、[A3]、[A26]、[F1]、[F2]。
- D debug 与当前实现差异: [DL45]、[DLS45]、[P26]、[I26]、[N26]、[S26]、[F26]、[TPA26]。
- 官方说明与工具: [W45]、[W26]、[WD]、[WFF]、[WPID]、[WDEBUG]、[WRPM]、[U1]、[U2]、[E1]。
- DSP 和方法边界: [D1]、[D2]、[D3]、[D4]、[D5]、[D6]; 原作者入口: [PT1]、[PT2]、[PT3]。

[V45]: https://github.com/betaflight/betaflight/releases/tag/4.5.2
[T45]: https://api.github.com/repos/betaflight/betaflight/git/ref/tags/4.5.2
[V26]: https://github.com/betaflight/betaflight/releases/tag/2026.6.2
[T26]: https://api.github.com/repos/betaflight/betaflight/git/ref/tags/2026.6.2
[B1]: https://github.com/betaflight/betaflight/blob/024f8e13d4e642eb6a380308685b9ea3aa3ef1a2/src/main/blackbox/blackbox.c#L182-L269
[B2]: https://github.com/betaflight/betaflight/blob/024f8e13d4e642eb6a380308685b9ea3aa3ef1a2/src/main/blackbox/blackbox.c#L1126-L1175
[B3]: https://github.com/betaflight/betaflight/blob/024f8e13d4e642eb6a380308685b9ea3aa3ef1a2/src/main/blackbox/blackbox.c#L460-L536
[B4]: https://github.com/betaflight/betaflight/blob/024f8e13d4e642eb6a380308685b9ea3aa3ef1a2/src/main/blackbox/blackbox.c#L1361-L1402
[B5]: https://github.com/betaflight/betaflight/blob/024f8e13d4e642eb6a380308685b9ea3aa3ef1a2/src/main/blackbox/blackbox.c#L322-L343
[B6]: https://github.com/betaflight/betaflight/blob/024f8e13d4e642eb6a380308685b9ea3aa3ef1a2/src/main/blackbox/blackbox.c#L2075-L2096
[B7]: https://github.com/betaflight/betaflight/blob/024f8e13d4e642eb6a380308685b9ea3aa3ef1a2/src/main/blackbox/blackbox.c#L1749-L1756
[B26]: https://github.com/betaflight/betaflight/blob/e0b7bb01b17b21351057e9ead2d1ab39dd44fa16/src/main/blackbox/blackbox.c#L1254-L1306
[B26F]: https://github.com/betaflight/betaflight/blob/e0b7bb01b17b21351057e9ead2d1ab39dd44fa16/src/main/blackbox/blackbox.c#L199-L300
[G1]: https://github.com/betaflight/betaflight/blob/024f8e13d4e642eb6a380308685b9ea3aa3ef1a2/src/main/sensors/gyro.c#L389-L455
[G2]: https://github.com/betaflight/betaflight/blob/024f8e13d4e642eb6a380308685b9ea3aa3ef1a2/src/main/sensors/gyro_init.c#L246-L268
[G3]: https://github.com/betaflight/betaflight/blob/024f8e13d4e642eb6a380308685b9ea3aa3ef1a2/src/main/sensors/gyro_filter_impl.c#L22-L90
[G26]: https://github.com/betaflight/betaflight/blob/e0b7bb01b17b21351057e9ead2d1ab39dd44fa16/src/main/sensors/gyro.c#L449-L459
[R1]: https://github.com/betaflight/betaflight/blob/024f8e13d4e642eb6a380308685b9ea3aa3ef1a2/src/main/flight/rpm_filter.c#L71-L190
[R2]: https://github.com/betaflight/betaflight/blob/024f8e13d4e642eb6a380308685b9ea3aa3ef1a2/src/main/drivers/dshot.c#L148-L160
[R3]: https://github.com/betaflight/betaflight/blob/024f8e13d4e642eb6a380308685b9ea3aa3ef1a2/src/main/drivers/dshot.c#L292-L343
[R26]: https://github.com/betaflight/betaflight/blob/e0b7bb01b17b21351057e9ead2d1ab39dd44fa16/src/main/drivers/dshot.c#L184-L191
[ARM45]: https://github.com/betaflight/betaflight/blob/024f8e13d4e642eb6a380308685b9ea3aa3ef1a2/src/main/fc/core.c#L364-L370
[ACC1]: https://github.com/betaflight/betaflight/blob/024f8e13d4e642eb6a380308685b9ea3aa3ef1a2/src/main/sensors/acceleration.c#L44-L84
[ACC2]: https://www.analog.com/en/resources/app-notes/an-1057.html
[P1]: https://github.com/betaflight/betaflight/blob/024f8e13d4e642eb6a380308685b9ea3aa3ef1a2/src/main/flight/pid_init.c#L396-L434
[P2]: https://github.com/betaflight/betaflight/blob/024f8e13d4e642eb6a380308685b9ea3aa3ef1a2/src/main/flight/pid.c#L1017-L1081
[P3]: https://github.com/betaflight/betaflight/blob/024f8e13d4e642eb6a380308685b9ea3aa3ef1a2/src/main/flight/pid.c#L944-L993
[P4]: https://github.com/betaflight/betaflight/blob/024f8e13d4e642eb6a380308685b9ea3aa3ef1a2/src/main/flight/pid.c#L280-L295
[P5]: https://github.com/betaflight/betaflight/blob/024f8e13d4e642eb6a380308685b9ea3aa3ef1a2/src/main/flight/pid.c#L796-L800
[DL45]: https://github.com/betaflight/betaflight/blob/024f8e13d4e642eb6a380308685b9ea3aa3ef1a2/src/main/flight/pid.c#L864-L878
[DLS45]: https://github.com/betaflight/betaflight/blob/024f8e13d4e642eb6a380308685b9ea3aa3ef1a2/src/main/flight/pid.c#L248-L250
[S45]: https://github.com/betaflight/betaflight/blob/024f8e13d4e642eb6a380308685b9ea3aa3ef1a2/src/main/config/simplified_tuning.c#L31-L114
[C45]: https://github.com/betaflight/betaflight/blob/024f8e13d4e642eb6a380308685b9ea3aa3ef1a2/src/main/cli/settings.c#L1190-L1254
[N45]: https://github.com/betaflight/betaflight/blob/024f8e13d4e642eb6a380308685b9ea3aa3ef1a2/src/main/fc/parameter_names.h#L79-L130
[M1]: https://github.com/betaflight/betaflight/blob/024f8e13d4e642eb6a380308685b9ea3aa3ef1a2/src/main/flight/mixer.c#L643-L677
[A1]: https://github.com/betaflight/betaflight/blob/024f8e13d4e642eb6a380308685b9ea3aa3ef1a2/src/main/flight/pid.c#L298-L316
[A2]: https://github.com/betaflight/betaflight/blob/024f8e13d4e642eb6a380308685b9ea3aa3ef1a2/src/main/flight/pid.c#L845-L855
[A3]: https://github.com/betaflight/betaflight/blob/024f8e13d4e642eb6a380308685b9ea3aa3ef1a2/src/main/flight/pid.c#L1114-L1123
[A26]: https://github.com/betaflight/betaflight/blob/e0b7bb01b17b21351057e9ead2d1ab39dd44fa16/src/main/flight/pid.c#L465-L483
[F1]: https://github.com/betaflight/betaflight/blob/024f8e13d4e642eb6a380308685b9ea3aa3ef1a2/src/main/fc/rc.c#L499-L624
[F2]: https://github.com/betaflight/betaflight/blob/024f8e13d4e642eb6a380308685b9ea3aa3ef1a2/src/main/fc/rc.c#L468-L480
[P26]: https://github.com/betaflight/betaflight/blob/e0b7bb01b17b21351057e9ead2d1ab39dd44fa16/src/main/flight/pid.c#L1347-L1375
[I26]: https://github.com/betaflight/betaflight/blob/e0b7bb01b17b21351057e9ead2d1ab39dd44fa16/src/main/flight/pid_init.c#L495-L507
[N26]: https://github.com/betaflight/betaflight/blob/e0b7bb01b17b21351057e9ead2d1ab39dd44fa16/src/main/fc/parameter_names.h#L121-L156
[S26]: https://github.com/betaflight/betaflight/blob/e0b7bb01b17b21351057e9ead2d1ab39dd44fa16/src/main/config/simplified_tuning.c#L31-L60
[F26]: https://github.com/betaflight/betaflight/blob/e0b7bb01b17b21351057e9ead2d1ab39dd44fa16/src/main/fc/rc.c#L496-L535
[TPA26]: https://github.com/betaflight/betaflight/blob/e0b7bb01b17b21351057e9ead2d1ab39dd44fa16/src/main/flight/pid.c#L264-L272
[W45]: https://betaflight.com/docs/wiki/release/Betaflight-4-5-Release-Notes#17-blackbox-and-logging-updates
[W26]: https://betaflight.com/docs/wiki/release/Betaflight-2026-6-Release-Notes
[WD]: https://betaflight.com/docs/wiki/guides/current/Dynamic-D
[WFF]: https://betaflight.com/docs/wiki/guides/current/Feed-Forward-2-0
[WPID]: https://betaflight.com/docs/wiki/app/pid-tuning-tab
[WDEBUG]: https://betaflight.com/docs/wiki/guides/current/Debug-Modes#cli-information-commands
[WRPM]: https://betaflight.com/docs/wiki/guides/current/DSHOT-RPM-Filtering
[U1]: https://github.com/betaflight/blackbox-tools/blob/d89f96b983d0f5c8f053acf003ee2998b02b5b0f/src/blackbox_decode.c#L190-L215
[U2]: https://github.com/betaflight/blackbox-tools/blob/d89f96b983d0f5c8f053acf003ee2998b02b5b0f/Readme.md#L16-L60
[E1]: https://github.com/betaflight/blackbox-log-viewer/blob/e179902df4e38f24d4b61f114bf856a196c995be/src/flightlog_fields_presenter.js#L1633-L1697
[D1]: https://docs.scipy.org/doc/scipy-1.16.2/reference/generated/scipy.signal.welch.html
[D2]: https://docs.scipy.org/doc/scipy-1.16.2/reference/generated/scipy.signal.coherence.html
[D3]: https://docs.scipy.org/doc/scipy-1.16.2/reference/generated/scipy.signal.csd.html
[D4]: https://docs.scipy.org/doc/scipy-1.16.2/reference/generated/scipy.signal.resample_poly.html
[D5]: https://www.mathworks.com/help/signal/ref/tfestimate.html
[D6]: https://docs.scipy.org/doc/scipy-1.16.2/reference/generated/scipy.signal.sosfiltfilt.html
[PT1]: https://github.com/bw1129/PIDtoolbox
[PT2]: https://raw.githubusercontent.com/bw1129/PIDtoolbox/master/PTstepcalc.m
[PT3]: https://pidtoolbox.com/
