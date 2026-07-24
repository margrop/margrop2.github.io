---
title: Hugging Face × Pollen Robotics 联合发布 Grabette：开源手持机器人数据采集器，BOM 不到 500 欧、用人类手掌就能给机器人攒训练集——一份 5 分钟读得懂的官方原版解读
categories:
  - ai_tech
tags:
  - Hugging Face
  - Pollen Robotics
  - Grabette
  - Gripette
  - LeRobot
  - 机器人数据采集
  - 6-DoF SLAM
  - Physical AI
  - AI Tech
cover: 'https://picsum.photos/seed/2026-07-24-hf-grabette-pollen-robotics-leRobot/1600/900'
coverWidth: 1600
coverHeight: 900
date: 2026-07-24 21:30:00
---

> 笔名：小六 / 上海 / 1995 女 / 某互联网公司工程师

![Hugging Face × Pollen Robotics Grabette：开源手持机器人数据采集器，BOM €490，给机器人攒训练集像拍视频一样简单](https://picsum.photos/seed/2026-07-24-hf-grabette-pollen-robotics-leRobot/1600/900)

## 一句话结论

Hugging Face 在 2026 年 7 月 21 日博客上发布了一篇题为 **"Grabette: an open system to record robot-manipulation data"** 的文章，联合法国的 Pollen Robotics 团队开源了一套手持机器人数据采集硬件 **Grabette** 和它的机械手孪生 **Gripette**。核心结论是：

> **机器人学习的瓶颈不是模型，是数据；Grabette 把"采集一份机器人操作示范"这件事的成本从"租一个实验室+真机器人+遥操作设备"压到"一个人手 + 一个 €490 的手持设备 + 浏览器"——数据集直接落进 LeRobot + Hugging Face Hub 标准格式。**

官方来源：[huggingface.co/blog/grabette](https://huggingface.co/blog/grabette)，作者 Steve Nguyen 等 6 人（Pollen Robotics），发布日期 2026-07-21。

这件事对工程团队的真实意义不在"又一个开源机器人项目"，而在**"机器人数据采集第一次有了'像拍视频一样简单'的官方背书硬件形态"**——这条链路一旦跑通，机器人开源生态会从"几个大实验室独占数据集"变成"全球开发者众包数据集"。下面把官方原版的设计、硬件规格、和工程团队可以立刻借鉴的最小工作流一起拆开。

## 发生了什么

Pollen Robotics 是一家法国的开源机器人公司，过去几年一直在做开源 humanoid 和 dual-arm 平台。这次和 Hugging Face 联合发布的 Grabette 是一套**完全开源的硬件 + 软件**，包含三件东西：

```text
1. Grabette
   -> 手持数据采集器（相机 + IMU + 夹爪）
   -> BOM 成本约 €490
   -> 由人类手持操作
   -> 录制 "人类示范的操作任务"

2. Gripette
   -> 电动夹爪（相机 + 两个舵机）
   -> BOM 成本约 €120
   -> 装在真实或仿真的机械臂末端
   -> 复现 Grabette 录制的轨迹

3. Capture + Process Pipeline
   -> 树莓派上的本地采集服务
   -> 浏览器里运行的 SLAM + 数据处理
   -> 输出标准 LeRobot dataset
   -> 直接 push 到 Hugging Face Hub
```

最关键的工程动作不是某个硬件参数，而是**输出格式**：Grabette 录完一次演示，处理后得到的不是某种私有格式，而是 **camera-local 6-DoF Cartesian pose + gripper state**——这是 LeRobot 已经定义好的标准 dataset 格式。也就是说，**录完一份数据，可以直接喂给任何支持 LeRobot 的训练 pipeline**（ACT、Diffusion Policy、VLA 等）。

这件事对开源生态的价值，类似当年 ImageNet 把"图像分类数据集格式"标准化之后的连锁反应——**格式先于内容，生态才能长出来**。

## 技术细节

### 1. 为什么"用人类手掌"是一个数据采集范式突破

机器人学习的传统数据采集路径是：

```text
传统路径
  -> 你需要一台真实机械臂
  -> 需要遥操作设备（VR 头显 + 控制器 / 主从臂）
  -> 需要一个安全围栏 / 实验室环境
  -> 需要一个会调遥操作的人
  -> 每个示范 30-60 分钟
  -> 单次实验成本 $1000+
```

这套路径是过去十年"机器人数据集稀缺"的根本原因。**不是没有人想贡献数据，是"贡献"这个动作的门槛太高**。

Grabette 的核心反直觉是：

```text
你不需要一台机器人来给机器人攒数据
你只需要
  -> 一只人类手掌
  -> 一个手持夹爪
  -> 一个摄像头
  -> 一种方法从视频里恢复 6-DoF 轨迹
```

这个想法不是 Grabette 原创——Stanford 2023 年的 **UMI（Universal Manipulation Interface）** 早就证明这条路可行。但 UMI 的门槛是"需要自己攒硬件、需要自己写 SLAM、需要自己整理数据格式"。**Grabette 把 UMI 走过的所有"自己"都封装成"开箱即用"**。

博客原话：

> "The bottleneck isn't the model. It's the data."

这句话是整篇博客的论点。机器人有能力的 policy 架构（transformer-based VLA、diffusion policy、flow matching policy、甚至 world model），**缺的是大规模、多样化的真实世界操作数据**。Grabette 解决的是最后这条。

### 2. 硬件规格：双相机 + IMU + 树莓派，BOM €490

Grabette 整机的 BOM（Bill of Materials）控制在 €490 左右，拆开来是：

```text
组件                        数量    角色
─────────────────────────────────────────────────────
Pi Camera（广角鱼眼）         1      "wrist camera" 视角
OAK-D 深度相机                1      6-DoF SLAM 跟踪
IMU（板载）                   1      帧间运动学约束
磁编码器                      1      夹爪开合度
树莓派                        1      本地采集 + 同步
手持夹爪骨架                  1      3D 打印 + 标准件
─────────────────────────────────────────────────────
                                合计约 €490
```

两个相机"分工明确"是文章强调的设计点：

```text
广角鱼眼（cheap）
   -> 负责"policy 看世界"的视角
   -> 高帧率、宽视野、给 policy 训练用

RGBD 相机（OAK-D）
   -> 负责"6-DoF 轨迹恢复"的高精度跟踪
   -> 不进 policy 输入
   -> 专做 SLAM
```

为什么不能一个相机做两件事？**policy 训练需要的视角和 SLAM 需要的精度，对相机参数的要求是冲突的**。一个广角能拍全场景，但 SLAM 精度差；一个高精度适合 SLAM，但视野窄、policy 训练时缺上下文。**拆成两个相机是经过权衡的工程决策**，不是"硬件不够所以加一个"。

### 3. Gripette 是 Grabette 的"机械孪生"

只有采集硬件，机器人学不到任何东西。**机器人的 policy 训练是在仿真或真实机械臂上进行的，Grabette 录的"人手操作"必须能被一个真实或仿真的机械臂复现**。

Gripette 就是这件事的执行端：

```text
Gripette BOM 约 €120
   -> 一个相机（看场景）
   -> 两个舵机（开合夹爪）
   -> 标准件 + 3D 打印外壳
   -> 装在任何机械臂末端（UR、xArm、Franka、OpenArm 等）
```

整套家族共享同一份"硬件 DNA"——相同的夹爪几何、相同的相机相对位置、相同的 ROS 节点名。这意味着**在 Grabette 上录的数据，可以直接让装在 UR5 上的 Gripette 复现**。如果换成 Franka 装的 Gripette，policy 输入可能需要微调，但数据格式不变。

博客里还提到一个细节：**Gripette 既可以装在真实机械臂上，也可以装在仿真机械臂上**。这意味着 Grabette 的数据可以同时用于 sim-to-real 和 real-to-real 训练。

### 4. 6-DoF 恢复靠 SLAM，不是手写

Grabette 不是用任何"专用 marker"或"动作捕捉"来恢复 6-DoF 轨迹。它用的是一个**普通 OAK-D 深度相机 + SLAM**。

这意味着：

```text
1. 你不需要昂贵的动作捕捉系统（Vicon、OptiTrack）
2. 你不需要在场景里贴 marker
3. 你可以在 "in the wild" 任何环境里录制
   -> 家里、办公室、工厂、户外
4. SLAM 自动恢复 6-DoF pose + RGBD 流
```

这是 UMI 路线的关键优势，也是 Grabette 能把单次采集成本压到 €490 的核心原因——**没有任何外部依赖**。

### 5. 输出格式：LeRobot 标准 + Hugging Face Hub

Grabette 处理 pipeline 输出的不是某种私有格式，而是 **LeRobot dataset**。LeRobot 是 Hugging Face 在 2024-2025 年推的开源机器人学习框架，已经定义好了：

```text
- dataset schema（相机流、关节角、夹爪状态）
- 标准化 transform（图像 resize、joint normalize）
- 训练 pipeline 接口（ACT、Diffusion Policy、VLA）
- Hub 集成（一键 push / pull dataset）
```

Grabette 处理完一次演示后，输出一个 LeRobot 标准 dataset 目录，**可以直接 push 到 Hugging Face Hub**。任何装了 LeRobot 的下游训练 pipeline 都可以直接 `load_dataset("your-name/your-grabette-dataset")`。

```python
# 下游用户加载 Grabette dataset 的最小代码
from lerobot import load_dataset

ds = load_dataset("pollen-robotics/example-grabette-dataset")
# dataset 已经是 LeRobot 标准格式
# 可以直接喂给 ACT / Diffusion Policy / VLA
```

### 6. 不需要本地编译：浏览器 + Raspberry Pi

博客强调 **"run from your browser with nothing to install"**。

```text
传统 SLAM 工具链
   -> 安装 ROS
   -> 编译 ORB-SLAM3 / DROID-SLAM
   -> 配置 launch file
   -> 解决依赖冲突
   -> 调相机标定

Grabette 工具链
   -> 树莓派上的采集服务（一个 docker image）
   -> 浏览器里跑处理 pipeline（Hugging Face Space）
   -> 数据通过 Hub 流转
   -> 整个流程不需要你本地编译
```

"no local compile"是这条链路能众包的关键。**如果每个想贡献数据的人都要先调通 ORB-SLAM3，生态系统根本起不来**。把所有重活推到浏览器/HF Space，让贡献者只关心"我要演示什么任务"，这是 Grabette 最重要的工程决策。

## 对 Agent / 工程的影响

这件事对实际做 robotics 团队的工程影响有三条：

**第一，机器人数据集的成本结构变了。** 过去一份 "10,000 条真实操作示范" 的数据集，实验室搭建成本在 $50K-100K；用 Grabette + 众包，理论上可以压到 $10K 量级（500 个贡献者 × €490 设备 × 20 次/天）。**对做 VLA / manipulation policy 的团队，这是一条立刻可以尝试的新路径。**

**第二，LeRobot + Hugging Face Hub 路线是 "2026 年 robotics 的 Linux 时刻"。** 当数据集格式、训练框架、分发渠道都标准化，开源贡献者可以像当年 Linux 一样众包机器人数据集。**任何还在用私有 dataset 格式的 robotics 团队，都值得把 LeRobot 评估一次**。

**第三，"采集硬件"和"训练框架"解耦了。** 过去 robotics 数据采集工具都是和某个特定框架绑死的（RTX + ROS + MoveIt、ALOHA + ACT 等）。Grabette 把采集做成"输出 LeRobot 标准"，训练 pipeline 可以自由切换。**这意味着机器人学习可能从 "垂直整合" 走向 "水平分工"**——专门做采集、专门做训练、专门做部署。

短期不建议碰的场景：

```text
- 工业级安全要求（机械臂碰撞保护、紧急停止）
- 高精度亚毫米级轨迹（SLAM 精度有限）
- 高速运动任务（树莓派的处理时延 ~50ms 起步）
```

## 我的判断

把这篇文章的结论压成三句话，给 robotics / agent 团队作为决策依据：

1. **机器人学习的瓶颈正在从 "模型" 切到 "数据"，而 Grabette 把 "贡献数据" 这个动作的门槛从 "实验室" 压到 "拍视频"**。这条链路一旦规模化，2026-2027 年的开源 VLA 模型会出现一波明显的"数据集红利"。

2. **LeRobot 标准格式是这次发布的最被低估的资产**。硬件可以抄，pipeline 可以重写，但 "一份数据能被任何下游 framework 直接用" 的标准地位是抢不走的。**2026 年下半年做 robotics 选型，LeRobot 应该是默认起点**，不是可选项。

3. **众包数据集的范式开始成立**。过去十年 robotics 一直卡在 "数据集是实验室专属资产"；Grabette + HF Hub 把这条路打通了。**对做机器人学习的团队，"自己攒数据" 不再是唯一选择，**"贡献到 Hub 换训练资源" 是新模式。

最后给一句也许不太中听的：**如果你的 robotics 项目还在 "用自己攒的私有数据集训练"——2026 年下半年开始，你会在 benchmark 上明显输给那些用 LeRobot + HF Hub 众包数据集训练的项目。** 不是你的模型差，是你的数据规模从一开始就被锁死了。

## Q&A

**Q1：来源/出处？**

A：Hugging Face 官方博客 [huggingface.co/blog/grabette](https://huggingface.co/blog/grabette)，2026-07-21 发布；硬件开源仓库见 Pollen Robotics GitHub；技术参考 Stanford UMI 论文。配套数据集可直接在 HF Hub 搜索 `pollen-robotics` 命名空间。

**Q2：能不能复现？怎么验证？**

A：最少复现路径（中等动手能力）：

```text
1. 准备一个树莓派 4B/5、一个 OAK-D Lite、一个 Pi Camera
2. 克隆 Pollen Robotics 的 Grabette 仓库
3. 按照 README 把硬件装好
4. 启动 capture service
5. 录制一个"拿起杯子"或"开门把手"的操作
6. 浏览器打开 HF Space 跑处理 pipeline
7. 把生成的 LeRobot dataset push 到 HF Hub
8. 加载这个 dataset，训练一个 ACT policy
9. 把训练好的 policy 部署到 Gripette + 任意机械臂
```

**Q3：适用边界是什么？**

A：操作任务复杂度受限——**单手 6-DoF 内的任务都能采，双手协调任务、柔性物体操作、高速运动任务目前不在覆盖范围**。BOM €490 的成本适合个人/小团队，**工业级精度/安全要求还需要更高规格硬件**。

**Q4：和 UMI 比有什么改进？**

A：UMI 是 Grabette 的"灵感来源"，两者核心思路一致（手持 + SLAM + 6-DoF 恢复）。Grabette 在三件事上比 UMI 友好：(1) 完整 BOM 清单 + 3D 打印文件，**不用自己攒硬件**；(2) 浏览器处理 pipeline，**不用自己装 ROS / 编译 SLAM**；(3) 输出 LeRobot 标准格式，**不用自己写 dataset adapter**。

**Q5：实施时容易踩的雷？**

A：3 个高频坑：(1) **树莓派 SD 卡 I/O 瓶颈**——同时录两个相机流时丢帧，建议用 USB3 SSD 启动；(2) **OAK-D 标定文件丢失**——SLAM 精度严重依赖标定，第一次启动必须按官方教程标定；(3) **leRobot 版本不匹配**——leRobot 还在快速演进，dataset 格式在不同版本间有 breaking change，**push 到 Hub 时锁版本**。

**Q6：众包数据集的安全 / 合规问题？**

A：博客没展开，但这是 Grabette 长期能不能跑通的核心问题。**人类手持操作录的视频包含环境信息（家庭、办公室）——Hub 公开 dataset 默认带 CC 协议，发布前需要明确告知贡献者哪些场景不能录（儿童、私密空间、敏感信息）。**

**Q7：和 Google RT-2 / Physical Intelligence 这类闭源大模型比，Grabette 的定位是什么？**

A：完全不同的层。RT-2 / π₀ 是 policy 模型，Grabette 是数据采集硬件。**两件事是互补的，不是竞争**。未来最可能的组合是：Grabette + 众包数据集训练出的开源 VLA，与 π₀ 这类闭源大模型在同一份 benchmark 上对比。**判断谁更强的关键变量是 "数据多样性"，不是 "模型架构"**。

---

> 字数自检：≥1500 个中文字符（不含 frontmatter）
> 隐私自检：IP 末 2 位打码，敏感词见 word-substitutions.md
> 封面 seed：`2026-07-24-hf-grabette-pollen-robotics-leRobot`（与今日 AI Diary 不同）

---

*作者：小六，一个在上海打工的普通工程师，今天读完 Grabette 之后已经在画图算"BOM €490 + 一只猫能不能当数据采集员"了*
