"""Maya 2022 / 2024 Qt UI: offline project + animator-authored expression sample workflow."""
import json,sys,datetime,uuid,copy,bisect
from pathlib import Path
from PySide2 import QtCore,QtGui,QtWidgets
from maya import cmds
from . import config,session,maya_session,groups,timing,maya_bridge
from .tracking_view import FrameCanvas,SignalPlot,DARK_STYLE
ROOT=config.ROOT
WINDOW=None


def maya_parent():
    try:
        from maya import OpenMayaUI
        import shiboken2
        pointer=OpenMayaUI.MQtUtil.mainWindow()
        return shiboken2.wrapInstance(int(pointer),QtWidgets.QWidget) if pointer else None
    except Exception:return None


class FaceInverseWindow(QtWidgets.QDialog):
    def __init__(self,parent=None):
        super(FaceInverseWindow,self).__init__(parent)
        self.setObjectName('FaceInverse04');self.setWindowTitle('FaceInverse 0.4 · 视频追踪与分组表情标定')
        self.setFont(QtGui.QFont('Microsoft YaHei',10))
        self.setStyleSheet(DARK_STYLE)
        self.resize(1150,960);self.setMinimumSize(760,650)
        self.path=None;self.data=None;self.base=None;self.tracking=None;self.job=None;self.loading=False
        layout=QtWidgets.QVBoxLayout(self);self.tabs=QtWidgets.QTabWidget();layout.addWidget(self.tabs)
        self.status=QtWidgets.QLabel('选择角色和视频创建项目，或打开已有 session.json');self.status.setWordWrap(True);layout.addWidget(self.status)
        self.make_project_tab()
        from .tracker_ui import TrackerWindow
        self.tracker_widget=TrackerWindow();self.tracker_widget.setParent(self.tabs);self.tracker_widget.setWindowFlags(QtCore.Qt.Widget);self.tabs.addTab(self.tracker_widget,'2 · Tracker')
        self.tracker_widget.probed.connect(self.on_video_probe)
        self.make_pose_tab();self.make_groups_tab();self.make_log_tab()
        self.play_timer=QtCore.QTimer(self);self.play_timer.timeout.connect(self.advance_frame)
        self.timer=QtCore.QTimer(self);self.timer.timeout.connect(self.poll_status);self.timer.start(900)
        self.clock=QtCore.QElapsedTimer();self.play_timer.setTimerType(QtCore.Qt.PreciseTimer)
        self.last_maya_time=None;self.follow_timer=QtCore.QTimer(self);self.follow_timer.timeout.connect(self.follow_maya);self.follow_timer.start(80)
    def button(self,text,name,action):
        b=QtWidgets.QPushButton(text);b.setObjectName(name);b.clicked.connect(lambda *_:self.safe(action));return b
    def safe(self,action):
        try:return action()
        except Exception as exc:
            self.status.setText(str(exc));self.log.appendPlainText(str(exc));return None
    def make_project_tab(self):
        page=QtWidgets.QWidget();form=QtWidgets.QFormLayout(page);self.fields={};current=config.settings()
        for key,label in [('scene','中性角色场景'),('maya_python','Maya 2022 / 2024 mayapy'),('plugin','RigLogic 插件（已有安装）'),('gui_root','Faceboard 根节点'),('mesh','输出脸部 Mesh'),('reference','头部参考节点'),('raw_node','只读表情诊断节点')]:
            field=QtWidgets.QLineEdit(str(current.get(key,'')));field.setObjectName(key);self.fields[key]=field
            if key in ('scene','maya_python','plugin'):
                row=QtWidgets.QWidget();box=QtWidgets.QHBoxLayout(row);box.setContentsMargins(0,0,0,0);box.addWidget(field)
                box.addWidget(self.button('选择',key+'_browse',lambda f=field:self.choose_file(f)));form.addRow(label,row)
            else:form.addRow(label,field)
        self.allow_newer_scene=QtWidgets.QCheckBox('尝试打开较新 Maya 场景（需重新验证角色变形）');self.allow_newer_scene.setChecked(bool(current.get('allow_newer_scene',False)));form.addRow(self.allow_newer_scene)
        self.video=QtWidgets.QLineEdit();self.video.setObjectName('video')
        row=QtWidgets.QWidget();box=QtWidgets.QHBoxLayout(row);box.setContentsMargins(0,0,0,0);box.addWidget(self.video);box.addWidget(self.button('选择视频','browse_video',lambda:self.choose_file(self.video)));form.addRow('参考视频',row)
        self.video_info=QtWidgets.QLabel('读取视频可查看原始帧率与方向');form.addRow(self.button('读取视频帧率 / 预览追踪前方向','probe_video',self.preview_source),self.video_info)
        self.output_fps=QtWidgets.QComboBox()
        for label,value in [('视频帧率（自动适配 Maya）',0),('24',24),('25',25),('29.97',29.97),('30',30),('50',50),('59.94',59.94),('60',60),('自定义 Maya 原生帧率',-1)]:self.output_fps.addItem(label,value)
        self.custom_fps=QtWidgets.QDoubleSpinBox();self.custom_fps.setDecimals(6);self.custom_fps.setRange(1,240);self.custom_fps.setValue(60)
        row=QtWidgets.QWidget();box=QtWidgets.QHBoxLayout(row);box.setContentsMargins(0,0,0,0);box.addWidget(self.output_fps);box.addWidget(self.custom_fps);form.addRow('Maya 输出帧率',row)
        self.pre_rotation=QtWidgets.QComboBox()
        for angle in (0,90,180,270):self.pre_rotation.addItem('顺时针 %d°'%angle,angle)
        self.auto_orientation=QtWidgets.QCheckBox('先读取视频方向元数据，再叠加此旋转');self.auto_orientation.setChecked(True)
        form.addRow('追踪前旋转（新项目）',self.pre_rotation);form.addRow(self.auto_orientation)
        self.start_frame=QtWidgets.QDoubleSpinBox();self.start_frame.setRange(-100000,1000000);self.start_frame.setValue(1);form.addRow('Maya 起始帧',self.start_frame)
        self.folder=QtWidgets.QLineEdit(str(ROOT/'projects'/'新项目'));self.folder.setObjectName('project_folder');form.addRow('项目目录（新目录）',self.folder)
        self.start=QtWidgets.QDoubleSpinBox();self.start.setRange(0,86400);form.addRow('截取起点 / 秒',self.start)
        self.duration=QtWidgets.QDoubleSpinBox();self.duration.setRange(0,86400);self.duration.setValue(15);self.duration.setSpecialValueText('全部');form.addRow('截取时长 / 秒',self.duration)
        form.addRow(self.button('新建项目：标定 → 追踪 → 初始动画','prepare_project',self.prepare_project))
        form.addRow(self.button('使用 Tracker 当前结果新建角色项目','prepare_from_tracker',self.prepare_from_tracker))
        form.addRow(self.button('打开已有项目 session.json','open_session',self.browse_session))
        form.addRow(self.button('将当前路径设置保存到工具','save_settings',self.save_settings))
        note=QtWidgets.QLabel('角色需为能正常评价的 MetaHuman 中性场景。仅操作现有 Faceboard；不修改 DNA/RBF/RigLogic。创建项目在独立进程进行，不替换当前场景。');note.setWordWrap(True);form.addRow(note)
        scroll=QtWidgets.QScrollArea();scroll.setWidgetResizable(True);scroll.setWidget(page);self.tabs.addTab(scroll,'1 · 项目与视频')
    def make_pose_tab(self):
        page=QtWidgets.QWidget();outer=QtWidgets.QVBoxLayout(page)
        self.image=FrameCanvas();self.image.setMinimumHeight(280);outer.addWidget(self.image,1)
        row=QtWidgets.QHBoxLayout();row.addWidget(QtWidgets.QLabel('参考显示旋转（不改追踪）'));self.display_rotation=QtWidgets.QComboBox()
        for angle in (0,90,180,270):self.display_rotation.addItem('%d°'%angle,angle)
        row.addWidget(self.display_rotation);self.overlay=QtWidgets.QCheckBox('显示追踪点');self.overlay.setChecked(True);row.addWidget(self.overlay)
        self.view_region=QtWidgets.QComboBox()
        for label,key in [('全脸','all'),('眉','brows'),('眼','eyes'),('嘴','mouth')]:self.view_region.addItem(label,key)
        row.addWidget(self.view_region);self.crop=QtWidgets.QCheckBox('放大所选区域');row.addWidget(self.crop);outer.addLayout(row)
        self.display_rotation.currentIndexChanged.connect(self.save_view)
        for widget in (self.view_region,self.overlay,self.crop):
            (widget.currentIndexChanged if isinstance(widget,QtWidgets.QComboBox) else widget.toggled).connect(lambda *_:self.goto_frame(self.frame.value(),False))
        row=QtWidgets.QHBoxLayout();self.frame=QtWidgets.QSpinBox();self.frame.setObjectName('video_frame');self.frame.setRange(0,0);self.slider=QtWidgets.QSlider(QtCore.Qt.Horizontal);self.slider.setRange(0,0)
        row.addWidget(QtWidgets.QLabel('视频帧（从 0 开始）'));row.addWidget(self.frame);row.addWidget(self.slider);outer.addLayout(row)
        self.frame.valueChanged.connect(self.goto_frame);self.slider.valueChanged.connect(self.frame.setValue)
        row=QtWidgets.QHBoxLayout();self.sync=QtWidgets.QCheckBox('切帧时同步 Maya');self.sync.setChecked(True);row.addWidget(self.sync)
        row.addWidget(self.button('播放 / 暂停参考','play_reference',self.toggle_play));row.addWidget(self.button('从当前 Maya 时间定位','pull_time',self.pull_time));row.addWidget(self.button('打开最近动画场景','open_scene',self.open_output));outer.addLayout(row)
        self.follow=QtWidgets.QCheckBox('跟随 Maya 时间轴');self.follow.setChecked(True);row.addWidget(self.follow)
        self.time_label=QtWidgets.QLabel();outer.addWidget(self.time_label)
        self.plot=SignalPlot();self.plot.setMaximumHeight(100);outer.addWidget(self.plot)
        row=QtWidgets.QHBoxLayout();self.suggestions=QtWidgets.QComboBox();row.addWidget(self.suggestions);row.addWidget(self.button('跳到建议表情','goto_suggestion',lambda:self.frame.setValue(int(self.suggestions.currentData() or 0))));row.addWidget(self.button('生成 / 更新参考缓存','cache_frames',self.cache_frames));outer.addLayout(row)
        form=QtWidgets.QFormLayout();self.label=QtWidgets.QLineEdit('关键表情');self.label.setObjectName('pose_label');form.addRow('样本名称',self.label)
        self.region=QtWidgets.QComboBox()
        for title,value in [('全部控制器','all'),('眉毛','brows'),('眼睛','eyes'),('嘴和鼻','mouth'),('下颌','jaw'),('仅 Maya 所选控制器','selected')]:self.region.addItem(title,value)
        self.region.setObjectName('pose_region');form.addRow('作用控制器',self.region)
        self.region.currentIndexChanged.connect(self.scope_view)
        self.mode=QtWidgets.QComboBox();self.mode.addItem('按相似表情传播（全片）','pose');self.mode.addItem('仅修正此帧附近（局部）','local');form.addRow('计算方式',self.mode)
        row=QtWidgets.QHBoxLayout();self.radius=QtWidgets.QDoubleSpinBox();self.radius.setRange(.05,10);self.radius.setValue(2.);self.radius.setSingleStep(.1)
        self.time_radius=QtWidgets.QDoubleSpinBox();self.time_radius.setRange(.01,30);self.time_radius.setValue(.5);row.addWidget(QtWidgets.QLabel('表情半径'));row.addWidget(self.radius);row.addWidget(QtWidgets.QLabel('局部半径 / 秒'));row.addWidget(self.time_radius);form.addRow(row)
        self.hard=QtWidgets.QCheckBox('关键帧精确保持所记录的值');self.hard.setChecked(True);form.addRow(self.hard);outer.addLayout(form)
        row=QtWidgets.QHBoxLayout();row.addWidget(self.button('记录新表情样本','capture_pose',self.capture_pose));row.addWidget(self.button('更新所选样本','update_pose',lambda:self.capture_pose(True)));outer.addLayout(row)
        self.table=QtWidgets.QTableWidget(0,6);self.table.setHorizontalHeaderLabels(['帧','名称','范围','模式','启用','精确']);self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows);self.table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection);self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers);self.table.setMinimumHeight(130);self.table.horizontalHeader().setStretchLastSection(True);outer.addWidget(self.table)
        self.table.itemDoubleClicked.connect(lambda *_:self.safe(self.select_sample_frame))
        row=QtWidgets.QHBoxLayout()
        for text,name,callback in [('载入所选样本到 Maya','apply_pose',self.apply_pose),('启用 / 禁用','toggle_pose',self.toggle_pose),('删除所选','delete_pose',self.delete_pose),('导出样本库','export_library',self.export_library),('导入样本库','import_library',self.import_library)]:row.addWidget(self.button(text,name,callback))
        outer.addLayout(row);outer.addWidget(self.button('按关键表情重新计算并烘焙新版本','solve_samples',self.solve_project))
        outer.addWidget(self.button('以所选输出帧率建立新版本（保留已记录 Pose）','retime_project',self.retime_project))
        scroll=QtWidgets.QScrollArea();scroll.setWidgetResizable(True);scroll.setWidget(page);self.pose_tab=scroll;self.tabs.addTab(scroll,'3 · 关键表情插帧')

    def make_groups_tab(self):
        page=QtWidgets.QWidget();box=QtWidgets.QVBoxLayout(page);row=QtWidgets.QHBoxLayout();self.group_choice=QtWidgets.QComboBox();row.addWidget(self.group_choice)
        row.addWidget(self.button('新建组','new_group',self.new_group));row.addWidget(self.button('重命名','rename_group',self.rename_group));row.addWidget(self.button('删除组','delete_group',self.delete_group));box.addLayout(row)
        splitter=QtWidgets.QSplitter();left=QtWidgets.QWidget();left_box=QtWidgets.QVBoxLayout(left);left_box.addWidget(QtWidgets.QLabel('该组控制器'));self.group_members=QtWidgets.QListWidget();self.group_members.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection);left_box.addWidget(self.group_members);splitter.addWidget(left)
        right=QtWidgets.QWidget();right_box=QtWidgets.QVBoxLayout(right);right_box.addWidget(QtWidgets.QLabel('已标定的 Faceboard 通道'));self.control_filter=QtWidgets.QLineEdit();self.control_filter.setPlaceholderText('筛选控制器');right_box.addWidget(self.control_filter)
        self.available_controls=QtWidgets.QListWidget();self.available_controls.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection);right_box.addWidget(self.available_controls);splitter.addWidget(right);box.addWidget(splitter)
        row=QtWidgets.QHBoxLayout();row.addWidget(self.button('将右侧选中通道加入组','add_group_controls',self.add_group_controls));row.addWidget(self.button('加入 Maya 所选控制器','add_maya_selection',self.add_maya_selection));row.addWidget(self.button('从组移除选中通道','remove_group_controls',self.remove_group_controls));box.addLayout(row)
        note=QtWidgets.QLabel('分组控制录制 Pose 时的通道范围。改组不会改写旧样本；新增已标定但尚未加入动画的通道会建立扩展工程新版本。未标定通道需重新标定。');note.setWordWrap(True);box.addWidget(note)
        self.group_choice.currentIndexChanged.connect(self.refresh_group_members);self.control_filter.textChanged.connect(self.refresh_available_controls);self.tabs.addTab(page,'4 · 控制器分组')

    def refresh_groups(self):
        if not self.data:return
        self.group_data=groups.available(self.data,self.base['plugs']);old=self.group_choice.currentData();self.group_choice.blockSignals(True);self.group_choice.clear()
        for key,group in self.group_data.items():self.group_choice.addItem(group['name'],key)
        idx=self.group_choice.findData(old);self.group_choice.setCurrentIndex(max(0,idx));self.group_choice.blockSignals(False)
        current=self.region.currentData();self.region.clear();self.region.addItem('全部控制器','all')
        for key,group in self.group_data.items():self.region.addItem('组 · '+group['name'],'group:'+key)
        self.region.addItem('仅 Maya 所选控制器','selected');idx=self.region.findData(current);self.region.setCurrentIndex(max(0,idx))
        self.refresh_group_members();self.refresh_available_controls()
    def refresh_group_members(self,*_):
        self.group_members.clear()
        if not self.data:return
        group=self.group_data.get(self.group_choice.currentData(),{})
        for plug in group.get('plugs',[]):
            item=QtWidgets.QListWidgetItem(plug.split('|')[-1]);item.setData(QtCore.Qt.UserRole,plug);item.setToolTip(plug);self.group_members.addItem(item)
    def refresh_available_controls(self,*_):
        self.available_controls.clear()
        if not self.data:return
        search=self.control_filter.text().lower()
        for control in self.cal['physical_controls']:
            plug=control['plug']
            if search not in plug.lower():continue
            title=plug.split('|')[-1]+(' · 可扩展' if plug not in self.base['plugs'] else '')
            item=QtWidgets.QListWidgetItem(title);item.setData(QtCore.Qt.UserRole,plug);item.setToolTip(plug);self.available_controls.addItem(item)
    def commit_groups(self):
        self.require_session();groups.validate(self.group_data,self.cal)
        missing={p for g in self.group_data.values() for p in g['plugs']}-set(self.base['plugs'])
        if missing:return self.fork_project(dict(groups=self.group_data))
        self.data=session.load(self.path);self.data['groups']=copy.deepcopy(self.group_data);session.save(self.path,self.data);self.refresh_groups()
    def new_group(self):
        self.require_session();name,ok=QtWidgets.QInputDialog.getText(self,'新建控制器组','组名')
        if ok and name.strip():self.group_data['custom_'+uuid.uuid4().hex[:8]]=dict(name=name.strip(),plugs=[]);self.commit_groups()
    def rename_group(self):
        self.require_session();key=self.group_choice.currentData();name,ok=QtWidgets.QInputDialog.getText(self,'重命名','组名',text=self.group_data[key]['name'])
        if ok and name.strip():self.group_data[key]['name']=name.strip();self.commit_groups()
    def delete_group(self):
        self.require_session();self.group_data.pop(self.group_choice.currentData());self.commit_groups()
    def append_group_controls(self,plugs):
        key=self.group_choice.currentData()
        if key is None:raise ValueError('请先新建或选择分组')
        current=self.group_data[key]['plugs'];self.group_data[key]['plugs']=list(dict.fromkeys(current+plugs));self.commit_groups()
    def add_group_controls(self):self.append_group_controls([i.data(QtCore.Qt.UserRole) for i in self.available_controls.selectedItems()])
    def add_maya_selection(self):
        self.require_session();selected=set(cmds.ls(selection=True,long=True) or [])
        plugs=[c['plug'] for c in self.cal['physical_controls'] if c['plug'] in selected or c['plug'].rsplit('.',1)[0] in selected]
        if not plugs:raise ValueError('所选控制器没有已标定通道；请先在项目中标定它')
        self.append_group_controls(plugs)
    def remove_group_controls(self):
        self.require_session();key=self.group_choice.currentData();remove={i.data(QtCore.Qt.UserRole) for i in self.group_members.selectedItems()}
        self.group_data[key]['plugs']=[p for p in self.group_data[key]['plugs'] if p not in remove];self.commit_groups()
    def selected_fps(self):
        value=self.output_fps.currentData();return self.custom_fps.value() if value==-1 else value
    def scope_view(self,*_):
        value=self.region.currentData() or 'all';key=value[6:] if value.startswith('group:') else value
        if key=='jaw':key='mouth'
        index=self.view_region.findData(key);self.view_region.setCurrentIndex(max(0,index))
    def preview_source(self):
        self.tracker_widget.source.setText(self.video.text());self.tracker_widget.pre_rotation.setCurrentIndex(self.tracker_widget.pre_rotation.findData(self.pre_rotation.currentData()));self.tracker_widget.auto.setChecked(self.auto_orientation.isChecked());self.tracker_widget.start.setValue(self.start.value());self.tracker_widget.preview();self.tabs.setCurrentWidget(self.tracker_widget)
    def on_video_probe(self,info):self.video_info.setText('源 %g fps → 自动 Maya %.6g fps · %s×%s · 方向元数据 %s°（按秒对齐）'%(info['fps'],timing.automatic_scene_rate(info['fps']),info['storage_width'],info['storage_height'],info['metadata_rotation_cw']))
    def fork_project(self,settings):
        self.require_session();destination=self.path.parent.parent/(self.path.parent.name+'_v04_'+uuid.uuid4().hex[:8])
        options=dict(settings,destination=str(destination));job=self.path.parent/('fork_'+uuid.uuid4().hex[:8]+'.json');session.save(job,options,False)
        self.pending_path=destination/'session.json';self.start_job(['-m','faceinverse.project','fork',str(self.path),'--settings',str(job)],self.path.parent)
    def retime_project(self):
        self.require_session();fps=self.selected_fps() or timing.automatic_scene_rate(self.tracking['fps']);self.fork_project(dict(scene_fps=fps,start_frame=self.start_frame.value()))
    def save_view(self,*_):
        if self.path and not self.loading:
            self.data=session.load(self.path);self.data.setdefault('view',{})['rotation_cw']=self.display_rotation.currentData();session.save(self.path,self.data)
        self.goto_frame(self.frame.value(),False)
    def follow_maya(self):
        if not self.path or not self.follow.isChecked() or self.loading or self.play_timer.isActive():return
        try:
            current=cmds.currentTime(query=True)
            if current==self.last_maya_time:return
            self.last_maya_time=current
            index=self.nearest_video_index(current)
            block=QtCore.QSignalBlocker(self.frame);self.frame.setValue(index);del block;self.goto_frame(index,False)
        except RuntimeError:pass
    def nearest_video_index(self,current=None):
        current=cmds.currentTime(query=True) if current is None else current
        project_frame=current/maya_bridge.frame_time(1.,self.base.get('scene_fps',24.))
        frames=self.base['frames'];position=bisect.bisect_left(frames,project_frame)
        return min({max(0,min(len(frames)-1,position)),max(0,min(len(frames)-1,position-1))},key=lambda i:abs(frames[i]-project_frame))
    def make_log_tab(self):
        page=QtWidgets.QWidget();box=QtWidgets.QVBoxLayout(page);self.log=QtWidgets.QPlainTextEdit();self.log.setReadOnly(True);box.addWidget(self.log)
        note=QtWidgets.QLabel('操作顺序：切参考帧 → 在 Maya 调整表情 → 记录样本 → 重算 → 打开新版本。样本和项目每次修改都有 history 备份；原始 baseline 不覆盖。相同表情矛盾时请禁用样本或改为局部模式。');note.setWordWrap(True);box.addWidget(note)
        box.addWidget(self.button('恢复项目历史快照','restore_history',self.restore_history));self.tabs.addTab(page,'日志与帮助')
    def closeEvent(self,event):
        if self.job and self.job.state()!=QtCore.QProcess.NotRunning:
            self.status.setText('后台任务仍在运行，请等待完成后关闭');event.ignore();return
        if self.tracker_widget.job and self.tracker_widget.job.state()!=QtCore.QProcess.NotRunning:event.ignore();self.status.setText('Tracker 仍在运行');return
        self.play_timer.stop();self.timer.stop();self.follow_timer.stop();self.tracker_widget.timer.stop();super(FaceInverseWindow,self).closeEvent(event)
    def toggle_play(self):
        self.require_session()
        if self.play_timer.isActive():self.play_timer.stop()
        else:self.play_origin=self.tracking['frames'][self.frame.value()]['time_seconds'];self.clock.start();self.play_timer.start(8)
    def advance_frame(self):
        if self.base:
            times=self.times;now=self.play_origin+self.clock.elapsed()/1000.
            self.frame.setValue(min(len(times)-1,max(0,bisect.bisect_right(times,now)-1)))
            if now>=times[-1]:self.play_timer.stop()
    def choose_file(self,field):
        path,_=QtWidgets.QFileDialog.getOpenFileName(self,'选择文件',field.text())
        if path:field.setText(path)
    def source_config(self):
        out=config.settings();out.update({key:field.text().strip() for key,field in self.fields.items()});out['allow_newer_scene']=self.allow_newer_scene.isChecked();out['maya_version']=str(cmds.about(version=True))
        out.update(output_fps=self.selected_fps(),pre_rotation=self.pre_rotation.currentData(),auto_orientation=self.auto_orientation.isChecked(),start_frame=self.start_frame.value());return out
    def save_settings(self):session.save(ROOT/'project_paths.json',self.source_config());self.status.setText('路径设置已保存')
    def prepare_project(self):
        folder=Path(self.folder.text()).resolve();folder.mkdir(parents=True,exist_ok=True)
        if (folder/'session.json').exists():raise ValueError('已有项目，请打开它或使用新目录')
        cfg=self.source_config();session.save(folder/'source_config.json',cfg,False)
        self.pending_path=folder/'session.json'
        self.start_job(['-m','faceinverse.project','prepare',str(folder),self.video.text(),'--config',str(folder/'source_config.json'),'--start',str(self.start.value()),'--duration',str(self.duration.value())],folder)
    def prepare_from_tracker(self):
        tracker=self.tracker_widget
        if not tracker.tracking or tracker.dirty:raise ValueError('请先在 Tracker 中完成并检查当前方向的追踪')
        folder=Path(self.folder.text()).resolve();folder.mkdir(parents=True,exist_ok=True)
        if (folder/'session.json').exists():raise ValueError('请选择一个新的角色项目目录')
        data=tracker.tracking;cfg=self.source_config();cfg.update(tracking_cache=str(tracker.folder/'tracking.json'),
            pre_rotation=data.get('requested_rotation_cw',0),auto_orientation=data.get('auto_orientation',True))
        session.save(folder/'source_config.json',cfg,False);self.pending_path=folder/'session.json'
        duration=data['frames'][-1]['time_seconds']+1./data['fps']
        self.start_job(['-m','faceinverse.project','prepare',str(folder),data['source'],'--config',str(folder/'source_config.json'),
            '--start',str(data.get('source_start_seconds',0.)),'--duration',str(duration)],folder)
    def start_job(self,args,folder):
        if self.job and self.job.state()!=QtCore.QProcess.NotRunning:raise ValueError('已有任务运行中，请等待完成')
        self.play_timer.stop();self.job=QtCore.QProcess(self);self.job.setProgram(config.python_executable(True));self.job.setArguments(args);self.job.setWorkingDirectory(str(ROOT))
        env=QtCore.QProcessEnvironment.systemEnvironment();env.remove('PYTHONHOME');env.insert('PYTHONPATH',str(ROOT));env.insert('OPENBLAS_NUM_THREADS','1');env.insert('OMP_NUM_THREADS','1');env.insert('MPLCONFIGDIR',str(folder/'cache'/'mpl'))
        self.job.setProcessEnvironment(env);self.job.setProcessChannelMode(QtCore.QProcess.MergedChannels)
        self.job.readyReadStandardOutput.connect(lambda:self.log.appendPlainText(bytes(self.job.readAllStandardOutput()).decode('utf8',errors='replace')))
        self.job.finished.connect(self.job_finished);self.job.errorOccurred.connect(lambda error:self.status.setText('后台进程无法启动: '+str(error)))
        self.job_folder=folder;self.status.setText('后台处理中，可在日志页查看结果');self.job.start()
    def job_finished(self,code,*_):
        self.status.setText('任务完成' if code==0 else '任务失败，请查看日志')
        if code==0 and hasattr(self,'pending_path') and self.pending_path.is_file():self.load_session(self.pending_path)
    def poll_status(self):
        if self.job and self.job.state()!=QtCore.QProcess.NotRunning:
            path=self.job_folder/'status.json'
            if path.is_file():
                try:self.status.setText(session.load(path).get('stage','处理中'))
                except (OSError,ValueError):pass
    def browse_session(self):
        path,_=QtWidgets.QFileDialog.getOpenFileName(self,'打开项目',str(ROOT/'projects'),'项目 JSON (*.json)')
        if path:self.load_session(path)
    def load_session(self,path):
        self.path=Path(path).resolve();self.data,self.cal,self.tracking,self.base=session.inputs(self.path)
        for key,field in self.fields.items():field.setText(str(self.data.get('config',{}).get(key,field.text())))
        self.loading=True;self.frame.setRange(0,len(self.base['frames'])-1);self.slider.setRange(0,len(self.base['frames'])-1)
        self.suggestions.clear()
        for item in session.suggestions(self.tracking):self.suggestions.addItem(item['label']+' · '+str(item['frame']),item['frame'])
        self.display_rotation.setCurrentIndex(self.display_rotation.findData(self.data.get('view',{}).get('rotation_cw',0)))
        self.loading=False;self.refresh_samples();self.refresh_groups();self.plot.rows=self.tracking['frames'];self.times=[r['time_seconds'] for r in self.tracking['frames']];self.last_maya_time=None;self.goto_frame(self.frame.value());self.tabs.setCurrentWidget(self.pose_tab);self.status.setText('项目已打开：'+str(self.path))
    def require_session(self):
        if self.path is None:raise ValueError('请先打开项目')
        if self.job and self.job.state()!=QtCore.QProcess.NotRunning:raise ValueError('计算中不能更改样本，请等待完成')
    def goto_frame(self,value,sync_time=True):
        if self.loading or self.path is None:return
        blocker=QtCore.QSignalBlocker(self.slider);self.slider.setValue(value);del blocker
        file=self.path.parent/'reference'/('%06d.jpg'%value)
        if file.is_file():
            self.image.region=self.view_region.currentData();self.image.overlay=self.overlay.isChecked();self.image.crop=self.crop.isChecked();self.image.set_frame(file,self.tracking['frames'][value],self.display_rotation.currentData() or 0)
        else:self.image.setText('参考帧缓存尚未生成，请点击“生成 / 更新参考缓存”')
        row=self.tracking['frames'][value];self.time_label.setText('视频帧 %d · 源帧 %s · %.4f 秒 · Maya %.4f 帧 @ %.6g fps'%(value,row.get('source_frame',value),row['time_seconds'],self.base['frames'][value],self.base.get('scene_fps',24.)));self.plot.current=value;self.plot.update()
        if sync_time and self.sync.isChecked():
            try:cmds.currentTime(maya_bridge.frame_time(self.base['frames'][value],self.base.get('scene_fps',24.)));self.last_maya_time=cmds.currentTime(query=True)
            except Exception as exc:self.status.setText(str(exc))
    def pull_time(self):
        self.require_session();index=self.nearest_video_index();self.frame.setValue(index);self.goto_frame(index)
    def selected_id(self):
        row=self.table.currentRow()
        if row<0:raise ValueError('请先选择样本')
        return self.table.item(row,0).data(QtCore.Qt.UserRole)
    def refresh_samples(self):
        if self.path is None:return
        self.data=session.load(self.path);self.table.setRowCount(len(self.data['samples']))
        for row,a in enumerate(self.data['samples']):
            scope=a['region'];definitions=groups.available(self.data,self.base['plugs'])
            scope=definitions.get(scope[6:],{}).get('name','已删除分组（保留原通道）') if scope.startswith('group:') else {'all':'全部','selected':'所选','brows':'眉毛','eyes':'眼睛','mouth':'嘴和鼻','jaw':'下颌'}.get(scope,scope)
            mode={'pose':'相似表情','local':'局部修正'}.get(a['mode'],a['mode'])
            for col,value in enumerate([a['frame'],a['label'],scope,mode,'是' if a.get('enabled',True) else '否','是' if a.get('hard',True) else '否']):
                item=QtWidgets.QTableWidgetItem(str(value));item.setData(QtCore.Qt.UserRole,a['id']);self.table.setItem(row,col,item)
        self.table.resizeColumnsToContents()
    def capture_pose(self,update=False):
        self.require_session();self.play_timer.stop();sample_id=self.selected_id() if update else None
        maya_session.capture_current(self.path,self.frame.value(),self.label.text(),self.region.currentData(),cmds.ls(selection=True,long=True) or [],self.mode.currentData(),self.hard.isChecked(),self.radius.value(),self.time_radius.value(),sample_id)
        self.refresh_samples();self.status.setText('表情样本已保存；点击重新计算后才会传播到全片')
    def select_sample_frame(self):
        a=next(a for a in self.data['samples'] if a['id']==self.selected_id())
        if a['clip_id']!=self.data['clip_id']:raise ValueError('此样本来自其他片段，只用于表情传播')
        self.frame.setValue(a['frame']);self.goto_frame(a['frame']);self.label.setText(a['label'])
    def apply_pose(self):self.require_session();maya_session.apply_sample(self.path,self.selected_id())
    def toggle_pose(self):
        self.require_session();ident=self.selected_id();a=next(a for a in self.data['samples'] if a['id']==ident);session.set_enabled(self.path,ident,not a.get('enabled',True));self.refresh_samples()
    def delete_pose(self):self.require_session();session.delete_sample(self.path,self.selected_id());self.refresh_samples()
    def export_library(self):
        self.require_session();path,_=QtWidgets.QFileDialog.getSaveFileName(self,'导出表情样本库',str(self.path.parent/'pose_library.json'),'JSON (*.json)')
        if path:session.export_library(self.path,path)
    def import_library(self):
        self.require_session();path,_=QtWidgets.QFileDialog.getOpenFileName(self,'导入兼容样本库',str(self.path.parent),'JSON (*.json)')
        if path:session.import_library(self.path,path);self.refresh_samples()
    def restore_history(self):
        self.require_session();path,_=QtWidgets.QFileDialog.getOpenFileName(self,'恢复项目历史',str(self.path.parent/'history'),'JSON (*.json)')
        if path:
            snapshot=session.load(path)
            if snapshot.get('session_id')!=self.data['session_id']:raise ValueError('历史快照不属于本项目')
            session.save(self.path,snapshot);self.load_session(self.path)
    def cache_frames(self):self.require_session();self.pending_path=self.path;self.start_job(['-m','faceinverse.project','cache',str(self.path)],self.path.parent)
    def solve_project(self):self.require_session();self.pending_path=self.path;self.start_job(['-m','faceinverse.project','solve',str(self.path)],self.path.parent)
    def open_output(self):
        self.require_session();path=self.path.parent/'baseline.mb';latest=self.path.parent/'latest.json'
        if latest.is_file():
            value=session.load(latest).get('scene')
            if value:path=session.resolve(self.path,value)
        if not path.is_file():raise ValueError('输出场景尚不存在')
        if cmds.file(query=True,modified=True):
            answer=QtWidgets.QMessageBox.question(self,'打开输出场景','当前场景有未保存更改。继续打开会放弃这些更改；已记录的样本库不受影响。',QtWidgets.QMessageBox.Yes|QtWidgets.QMessageBox.No,QtWidgets.QMessageBox.No)
            if answer!=QtWidgets.QMessageBox.Yes:return
        plugin=self.data['config'].get('plugin')
        if plugin:cmds.loadPlugin(plugin,quiet=True)
        cmds.file(str(path),open=True,force=True,prompt=False,executeScriptNodes=False)


def show():
    global WINDOW
    if WINDOW:
        try:
            if WINDOW.job and WINDOW.job.state()!=QtCore.QProcess.NotRunning:
                WINDOW.show();WINDOW.raise_();return WINDOW
            WINDOW.close();WINDOW.deleteLater()
        except RuntimeError:pass
    if QtWidgets.QApplication.instance() is None:raise RuntimeError('请从 Maya 2022 或 2024 交互界面启动工具')
    WINDOW=FaceInverseWindow(maya_parent());WINDOW.show();WINDOW.raise_();return WINDOW
