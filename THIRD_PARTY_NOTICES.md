# 第三方素材及归属

## CREMA-D

Crowd-sourced Emotional Multimodal Actors Dataset，作者项目：https://github.com/CheyneyComputerScience/CREMA-D 。

Cao H, Cooper DG, Keutmann MK, Gur RC, Nenkova A, Verma R. CREMA-D: Crowd-sourced Emotional Multimodal Actors Dataset. IEEE Transactions on Affective Computing. 2014;5(4):377–390. DOI: 10.1109/TAFFC.2014.2336244.

本机测试使用 1001_DFA_ANG_XX.flv 和 1001_DFA_HAP_XX.flv。数据库许可 ODbL 1.0：https://opendatacommons.org/licenses/odbl/1.0/ ，个别内容 DbCL 1.0：https://opendatacommons.org/licenses/dbcl/1.0/ 。上游 LICENSE.txt 完整保留为 docs/CREMA_D_LICENSE.txt。原始文件和对照输出只留本地，不随源码提交；公开再分发时仍须遵守这些条件。

## 公开讲话视频

The White House, 20160917 POTUS Weekly Address。来源页：https://commons.wikimedia.org/wiki/File:20160917_POTUS_Weekly_Address_HD.webm 。页面标注为美国联邦政府工作人员职务作品、公有领域。本项目仅用于非背书性质的面部动画测试，对照视频明确标注合成输出。

## 模型与软件

FaceLandmarker 模型从 Google 官方 MediaPipe 模型下载地址取得，来源及哈希见 test_assets.json；权重不入 Git。MediaPipe、NumPy、SciPy、OpenCV 和诊断渲染依赖按各自上游许可使用，完整版本在锁定文件中。本项目没有重新授权这些上游组件。

MetaHuman 角色及 Epic 插件属于用户本地现有资产，本项目不随源码分发它们。
