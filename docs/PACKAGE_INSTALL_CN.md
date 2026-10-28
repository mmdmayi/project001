> 0.4 工作台新增 Tracker、旋转、帧率和分组操作，见 WORKBENCH_V04_CN.md。下文保留基本安装与样本操作说明。

# FaceInverse 0.4 安装说明

支持 Windows x64、Maya 2022（Python 3 模式）和 Maya 2024；安装包默认目标由 release.json 指定。工具不分发 Maya、角色、DNA 或 Epic 插件；角色必须已能在目标电脑正常评价。

## 联网安装包

1. 完整解压到可写目录，例如 D:/Tools/FaceInverse。不要在压缩包内直接运行。
2. 双击 INSTALL.bat。首次会下载固定版本的独立 Python、库和官方模型。无需电脑预装 Python，不改系统 PATH，不向 Maya Python 装科学计算库。
3. 等待 Installation complete 和测试 OK。双击 VERIFY.bat 可再次验证。
4. 双击 OPEN_MAYA_TOOL.bat，或在 Maya Python 编辑器运行：

```python
import runpy
runpy.run_path(r'D:/Tools/FaceInverse/scripts/launch_ui.py')
```

界面使用 Maya 自带 PySide2，不需另装 Qt。

## 完整离线包

本地 dist 中的 offline-full 包包含 Python、依赖 Wheel 以及本用户已下载的模型；复制到其他电脑、解压后运行相同的 INSTALL.bat。安装时逐个校验 Wheel 和模型哈希。角色和 Epic 插件仍需在目标电脑配置。

联网小包安装后，视频处理在本地进行，不需要上传视频。依赖优先通过清华 PyPI 镜像安装，失败后尝试官方 PyPI，未关闭 TLS 或完整性检查。

## 固定依赖与手动补库

完整精确版本见 requirements-runtime.lock.txt。主要版本：Python 3.12.10、NumPy 1.26.4、SciPy 1.15.3、MediaPipe 0.10.21、OpenCV 4.11.0.86。预览和 ffmpeg 依赖也随安装器处理。

必要时可在工具目录手动补库（先让 INSTALL.bat 解压运行时）：

```bat
.runtime\python\python.exe -m pip install --no-build-isolation --target .runtime\python\Lib\site-packages -r requirements-runtime.lock.txt
```

不要用 mayapy 安装这些库。Maya 端只使用标准库和 Maya API。

## 目标电脑的设置

第一次在“项目与视频”页选择：中性角色场景、当前目标版本的 mayapy、已有 RigLogic 插件、Faceboard 根、输出脸部 Mesh、头部参考和只读诊断节点。标准命名通常为 gui / head_lod0_mesh / head_grp / CTRL_expressions，命名空间不同要相应调整。

默认自动查找标准位置的 Maya 和 MetaHuman for Maya 插件。安装在其他位置时手动选择。运行时安装通过不代表未知角色绑定通过；必须在那台电脑先完成角色标定。

## 迁移与排错

- 解压位置有中文和空格已实际测试。移动已安装目录后重新运行 INSTALL.bat，它会登记当前路径，已满足版本的库不会重新下载，不会清空项目。
- 项目数据在 projects 或你指定的项目目录；备份整个项目目录。源角色和源视频不被封进项目安装包，需另外保留。
- 原角色路径改变后，可编辑 session.json 的 config.scene / config.plugin / config.maya_python 为本机路径；不要改 baseline 数据。更换角色应重新建立项目和标定，不要强行复用。
- 模型文件采用内存加载，避免原生库中文路径问题；mayapy 作业采用编码传递，已在中文目录验证。
- 无可用 OpenGL 时仍可用 Maya 动画和样本计算；外部诊断渲染不是核心前提。
- 安装验证日志在 work/verify_install.json；项目步骤日志和 status.json 在各项目目录。

本机验证使用同一台 Windows 电脑上的干净目录和独立运行时，不能声称已在所有其他电脑或显卡实机验证。


## Maya 2022 版本

2022 专项安装、Python 3 模式、插件版本和跨电脑迁移见 MAYA2022_INSTALL_CN.md。0.3.1 默认关闭未标定的幅度补偿；请用新建项目采用新默认。保存本机路径设置后，运行 VERIFY_MAYA.bat 验证实际角色；VERIFY.bat 仅验证依赖和数值算法。
