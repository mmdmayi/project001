# Maya 2022 安装与迁移说明（FaceInverse 0.3.1）

适用：Windows x64、Maya 2022 的 Python 3 模式。Maya 2022 的 Python 2 模式不支持。也保留 Maya 2024 兼容路径。本包 release.json 指定默认目标为 2022，自动查找 Maya2022/bin/mayapy.exe 与 maya-2022 的已有 RigLogic 插件；不自动改用 2024。

## 在其他电脑安装

1. 目标电脑安装可正常运行的 Maya 2022，确认启动为 Python 3 模式。界面和插件由 Maya 提供；无需另装 Qt。
2. 安装该角色所需的 **Maya 2022 版本**执行插件。Maya 2024 的 mll 不能当作 2022 插件使用。角色、DNA 及插件由用户已有环境提供，工具不分发这些内容。
3. 完整解压安装包到可写目录，例如 D:/Tools/FaceInverse2022。离线完整包带固定运行时、38 个依赖 Wheel 和追踪模型；联网包首次安装需要网络。
4. 双击 INSTALL.bat，等待安装与测试完成。工具建立自己的 .runtime/python（Python 3.12.10），不向 Maya 的 Python 3.7 安装 NumPy、SciPy 或 MediaPipe，不改系统 PATH。
5. 双击 VERIFY.bat，确认依赖、追踪模型初始化与数值测试通过。
6. 双击 OPEN_MAYA_TOOL.bat；在界面选择本机中性角色场景、Maya2022/bin/mayapy.exe、对应 maya-2022/plugin/embeddedRL4.mll，检查 gui、head_lod0_mesh、head_grp、CTRL_expressions（有命名空间时填完整名称）。点击“将当前路径设置保存到工具”。
7. 双击 VERIFY_MAYA.bat，对本机配置执行真实 Faceboard 响应与 Mesh 变形检查。成功后在 work/verify_maya.json 记录实际宿主版本与非零 Mesh 响应。这比仅通过依赖验证多验证一层，但仍不等于视频表演精度已通过。
8. 按 USER_GUIDE_CN.md 创建视频项目、记录关键表情、按相似表情或局部方式重算，输出独立 Maya 场景。

## 已打开的 Maya 2022 中启动

在 Python 脚本编辑器运行（替换为实际解压路径）：

```python
import runpy
runpy.run_path(r'D:/Tools/FaceInverse2022/scripts/launch_ui.py')
```

建议在干净 Maya 会话启动；若已有其他路径的 faceinverse 模块被导入，重启 Maya 后使用新安装路径。

## 场景和素材迁移

- 建议使用在 Maya 2022 中确认可正常变形的中性角色场景。若来源是较新 Maya 场景，可在工具界面明确勾选“尝试打开较新 Maya 场景”；这只允许 Maya 尝试读取，不能保证任意新版本节点或材质兼容。生成的结果由实际运行的 Maya 2022 保存，源场景不覆盖。
- 角色所需 DNA、引用、纹理、其他插件及其本机路径仍须在目标电脑正确配置。工具不会重写 DNA 或重建绑定。安装包不包含本机 N 盘角色。
- 新包不携带开发机的 project_paths.json。初次安装按本机发现结果生成配置；所有路径可在界面修改保存。复制旧工程时同步迁移源素材并更新 session.json/config 的场景、插件和 mayapy 路径，以及追踪数据内的源视频路径。换角色时应重新标定。
- 移动已安装的工具文件夹后重新运行 INSTALL.bat，刷新隔离运行时的路径；无需删除项目。
- 若宿主版本与项目 maya_version 不一致，后台会明确失败，不会把一次 2024 运行冒充 2022 验证。

## 写实范围和验收

新包默认关闭未标定的张嘴/闭眼幅度辅助，不为风格化视频强行放大目标。已有旧工程不会自动重写 baseline；若要采用新默认，需新建项目重新追踪与求解。数值测试、UI 流程和实际 Rig 烘焙成功不等于真人表演逐帧准确还原，详见 REALISTIC_FIDELITY_AUDIT_CN.md。

本机可执行干净目录与隔离安装验证；无法据此声称每台其他电脑、任意角色及任意插件组合均通过。用上述 VERIFY_MAYA 在目标电脑检查实际角色。
