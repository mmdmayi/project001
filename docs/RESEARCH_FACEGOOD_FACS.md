# FACEGOOD 与 FACS 调研及本版决策

查询/访问：2026-10-28至29。先使用 agent-reach 路由，搜索连接和 Jina Reader 多次连接失败后，通过浏览器读取官网，再通过恢复的搜索工具核对技术原始资料。未以论坛转载作为算法依据。

## 官方 Wiki 地址（已核实入口）

[FACEGOOD 官网](https://www.avatary.com/p1) 的 Wiki 菜单实际打开：

[FACEGOOD Wiki EN](https://avatary.yuque.com/org-wiki-avatary-uhm530/uclqrt)

已读取 [Tracker Tracking System](https://avatary.yuque.com/org-wiki-avatary-uhm530/uclqrt/zvgkol0ka46atmhm)：公开工作流包含自动跟踪、按组检查、逐帧手工修正点位再计算。已读取 [Importing Video and Connecting to DCC](https://avatary.yuque.com/org-wiki-avatary-uhm530/uclqrt/hfg6fv1e2p4z6lha)：导入视频与DCC连接是独立阶段。

Wiki 目录还列有 [Control Rig Binding](https://avatary.yuque.com/org-wiki-avatary-uhm530/uclqrt/fepr05aqo55f2tur) 和 [Keyframe Solving](https://avatary.yuque.com/org-wiki-avatary-uhm530/uclqrt/cmxfbiwwhmtq6b5e)。本次这两页正文未成功获取，因此不据此断言其内部算法。

本版参考视频居中、区域叠点、时间线、检查标记、控制器分组与样本再计算这些操作原则，使用本工具已有的离线 MediaPipe 后端；不复制品牌外观，也未实现FACEGOOD的人工拖点训练模型。

## FACS 能帮助什么

[Paul Ekman Group 的 FACS 说明](https://www.paulekman.com/facial-action-coding-system/) 将可见面部动作拆解为动作单元，并给出观察和组合编码标准。它不是一个直接替换追踪器的自动识别算法。

[MediaPipe 官方说明](https://developers.google.cn/edge/mediapipe/solutions/vision/face_landmarker) 的输出包括478点与52个blendshape系数。将这些系数解释为经过验证的FACS强度或直接当成情绪真值，没有本版实验证据。

本版采用动作名称和AU相关线索提示，保留人工确认。改掉“无条件取最大值即认定微笑”，使用阈值、邻帧和相对嘴角几何作为保守候选门槛。此改动没有取得独立FACS标注测试集，不能宣称真实视频识别准确率提高了多少。

## 帧率、旋转及解算

[OpenCV Video I/O 官方属性说明](https://docs.opencv.org/4.x/d4/d15/group__videoio__flags__base.html) 提供时间戳与方向元数据/自动旋转属性。本版关闭隐式自动旋转，再显式应用方向元数据和用户输入角度；推理和参考缓存共用同一预处理。Maya参考显示旋转属于独立显示层。

[SciPy lsq_linear 文档](https://docs.scipy.org/doc/scipy-1.15.3/reference/generated/scipy.optimize.lsq_linear.html) 描述的是有界线性最小二乘子问题，其收敛解对该凸问题是全局解。这不证明整个演员到角色模型最优，也不证明折叠正负分支后的物理约束问题全局最优，更不代表视频表演还原无误。

遵照用户要求，未找到并验证更优替代方案前，不修改现有数值目标、时序参数或关键表情修正算法。以原版和新版同输入的数值结果对照，以及 solver.py/pose_solver.py 文件哈希复查来证明本轮保持数值核心。
