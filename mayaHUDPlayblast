# -*- coding: utf-8 -*-
"""
Playblast with HUD (creator & camera)  –  Fixed Layout Version
Author  : YourName
Version : 1.1  (Maya 2018+)
"""

import os
import maya.cmds as cmds

HUD_CREATOR = "HUD_creatorName"
HUD_CAMERA  = "HUD_cameraName"
WINDOW_NAME = "playblastHudWin"

def parse_creator_from_tex(tex_path):
    """根据纹理文件名解析制作人员姓名"""
    if not tex_path:
        return "Unknown"
    base = os.path.basename(tex_path)
    name, _ = os.path.splitext(base)
    return name.split("_")[-1]

def delete_hud_safely():
    """安全删除 HUD"""
    for hud in (HUD_CREATOR, HUD_CAMERA):
        if cmds.headsUpDisplay(hud, exists=True):
            cmds.headsUpDisplay(hud, remove=True)

def create_hud(creator, camera):
    """在屏幕左上角创建 HUD"""
    delete_hud_safely()
    cmds.headsUpDisplay(HUD_CREATOR,
                        section=1, block=0, blockSize="small",
                        label="Creator", command=lambda *args: creator)
    cmds.headsUpDisplay(HUD_CAMERA,
                        section=1, block=1, blockSize="small",
                        label="Camera",  command=lambda *args: camera)

def run_playblast(output_dir, creator, camera,
                  fmt="qt", codec="H.264", width=1280, height=720):
    """执行 playblast"""
    if not os.path.isdir(output_dir):
        os.makedirs(output_dir)
    create_hud(creator, camera)
    file_path = os.path.join(output_dir, f"{camera}_{creator}")
    try:
        cmds.playblast(filename=file_path,
                       forceOverwrite=True,
                       format=fmt,
                       compression=codec,
                       percent=100,
                       widthHeight=[width, height],
                       showOrnaments=True,
                       viewer=True)
    finally:
        delete_hud_safely()

# -------------------------  UI  ------------------------- #

class PlayblastHUDUI(object):
    def __init__(self):
        if cmds.window(WINDOW_NAME, exists=True):
            cmds.deleteUI(WINDOW_NAME)
        self.window = cmds.window(WINDOW_NAME,
                                  title=u"Playblast HUD 工具",
                                  sizeable=False)

        # **修正点：先建立一个布局容器**
        cmds.columnLayout(adjustableColumn=True)

        # 纹理文件路径
        self.tex_path_field = cmds.textFieldButtonGrp(
            label=u"纹理文件 (*.tex)：",
            buttonLabel=u"...",
            bc=self.browse_tex)

        # 摄像机下拉框
        self.camera_opt = cmds.optionMenuGrp(label=u"摄像机：")
        for cam in cmds.ls(type="camera", long=True):
            cmds.menuItem(label=cam)

        # 输出目录
        default_out = os.path.join(cmds.workspace(q=True, rd=True), "playblasts")
        self.out_dir_field = cmds.textFieldButtonGrp(
            label=u"输出目录：",
            text=default_out,
            buttonLabel=u"...",
            bc=self.browse_output)

        # Playblast 按钮
        cmds.button(label=u"开始 Playblast",
                    height=40,
                    command=self.do_playblast)

        cmds.showWindow(self.window)

    # --- 回调函数 ---
    def browse_tex(self, *_):
        paths = cmds.fileDialog2(fileMode=1, caption="选择 .tex 文件")
        if paths:
            cmds.textFieldButtonGrp(self.tex_path_field, e=True, text=paths[0])

    def browse_output(self, *_):
        paths = cmds.fileDialog2(fileMode=3, caption="选择输出目录")
        if paths:
            cmds.textFieldButtonGrp(self.out_dir_field, e=True, text=paths[0])

    def do_playblast(self, *_):
        tex_path = cmds.textFieldButtonGrp(self.tex_path_field, q=True, text=True)
        creator  = parse_creator_from_tex(tex_path)

        camera   = cmds.optionMenuGrp(self.camera_opt, q=True, v=True)
        out_dir  = cmds.textFieldButtonGrp(self.out_dir_field, q=True, text=True)

        run_playblast(out_dir, creator, camera)

# 直接运行
if __name__ == "__main__":
    PlayblastHUDUI()

