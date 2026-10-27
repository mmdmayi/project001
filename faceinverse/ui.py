"""Maya 2022 / 2024 Qt UI: offline project + animator-authored expression sample workflow."""
import json,sys
from pathlib import Path
from PySide2 import QtCore,QtGui,QtWidgets
from maya import cmds
from . import config,session,maya_session
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
        self.setObjectName('FaceInverse03');self.setWindowTitle('FaceInverse 0.3.1 · 关键表情标定')
        self.setFont(QtGui.QFont('Microsoft YaHei',10))
        self.resize(860,900);self.setMinimumSize(720,650)
        self.path=None;self.data=None;self.base=None;self.tracking=None;self.job=None;self.loading=False
        layout=QtWidgets.QVBoxLayout(self);self.tabs=QtWidgets.QTabWidget();layout.addWidget(self.tabs)
        self.status=QtWidgets.QLabel('选择角色和视频创建项目，或打开已有 session.json');self.status.setWordWrap(True);layout.addWidget(self.status)
        self.make_project_tab();self.make_pose_tab();self.make_log_tab()
        self.play_timer=QtCore.QTimer(self);self.play_timer.timeout.connect(self.advance_frame)
        self.timer=QtCore.QTimer(self);self.timer.timeout.connect(self.poll_status);self.timer.start(900)
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
        self.folder=QtWidgets.QLineEdit(str(ROOT/'projects'/'新项目'));self.folder.setObjectName('project_folder');form.addRow('项目目录（新目录）',self.folder)
        self.start=QtWidgets.QDoubleSpinBox();self.start.setRange(0,86400);form.addRow('截取起点 / 秒',self.start)
        self.duration=QtWidgets.QDoubleSpinBox();self.duration.setRange(0,86400);self.duration.setValue(15);self.duration.setSpecialValueText('全部');form.addRow('截取时长 / 秒',self.duration)
        form.addRow(self.button('新建项目：标定 → 追踪 → 初始动画','prepare_project',self.prepare_project))
        form.addRow(self.button('打开已有项目 session.json','open_session',self.browse_session))
        form.addRow(self.button('将当前路径设置保存到工具','save_settings',self.save_settings))
        note=QtWidgets.QLabel('角色需为能正常评价的 MetaHuman 中性场景。仅操作现有 Faceboard；不修改 DNA/RBF/RigLogic。创建项目在独立进程进行，不替换当前场景。');note.setWordWrap(True);form.addRow(note)
        self.tabs.addTab(page,'1 · 项目与视频')
    def make_pose_tab(self):
        page=QtWidgets.QWidget();outer=QtWidgets.QVBoxLayout(page)
        self.image=QtWidgets.QLabel('打开项目后显示参考视频帧');self.image.setAlignment(QtCore.Qt.AlignCenter);self.image.setMinimumHeight(235);self.image.setMaximumHeight(340);self.image.setStyleSheet('background:#20242b;color:#cbd2dc');outer.addWidget(self.image)
        row=QtWidgets.QHBoxLayout();self.frame=QtWidgets.QSpinBox();self.frame.setObjectName('video_frame');self.frame.setRange(0,0);self.slider=QtWidgets.QSlider(QtCore.Qt.Horizontal);self.slider.setRange(0,0)
        row.addWidget(QtWidgets.QLabel('视频帧（从 0 开始）'));row.addWidget(self.frame);row.addWidget(self.slider);outer.addLayout(row)
        self.frame.valueChanged.connect(self.goto_frame);self.slider.valueChanged.connect(self.frame.setValue)
        row=QtWidgets.QHBoxLayout();self.sync=QtWidgets.QCheckBox('切帧时同步 Maya');self.sync.setChecked(True);row.addWidget(self.sync)
        row.addWidget(self.button('播放 / 暂停参考','play_reference',self.toggle_play));row.addWidget(self.button('从当前 Maya 时间定位','pull_time',self.pull_time));row.addWidget(self.button('打开最近动画场景','open_scene',self.open_output));outer.addLayout(row)
        row=QtWidgets.QHBoxLayout();self.suggestions=QtWidgets.QComboBox();row.addWidget(self.suggestions);row.addWidget(self.button('跳到建议表情','goto_suggestion',lambda:self.frame.setValue(int(self.suggestions.currentData() or 0))));row.addWidget(self.button('生成 / 更新参考缓存','cache_frames',self.cache_frames));outer.addLayout(row)
        form=QtWidgets.QFormLayout();self.label=QtWidgets.QLineEdit('关键表情');self.label.setObjectName('pose_label');form.addRow('样本名称',self.label)
        self.region=QtWidgets.QComboBox()
        for title,value in [('全部控制器','all'),('眉毛','brows'),('眼睛','eyes'),('嘴和鼻','mouth'),('下颌','jaw'),('仅 Maya 所选控制器','selected')]:self.region.addItem(title,value)
        self.region.setObjectName('pose_region');form.addRow('作用控制器',self.region)
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
        scroll=QtWidgets.QScrollArea();scroll.setWidgetResizable(True);scroll.setWidget(page);self.tabs.addTab(scroll,'2 · 关键表情插帧')
    def make_log_tab(self):
        page=QtWidgets.QWidget();box=QtWidgets.QVBoxLayout(page);self.log=QtWidgets.QPlainTextEdit();self.log.setReadOnly(True);box.addWidget(self.log)
        note=QtWidgets.QLabel('操作顺序：切参考帧 → 在 Maya 调整表情 → 记录样本 → 重算 → 打开新版本。样本和项目每次修改都有 history 备份；原始 baseline 不覆盖。相同表情矛盾时请禁用样本或改为局部模式。');note.setWordWrap(True);box.addWidget(note)
        box.addWidget(self.button('恢复项目历史快照','restore_history',self.restore_history));self.tabs.addTab(page,'日志与帮助')
    def closeEvent(self,event):
        if self.job and self.job.state()!=QtCore.QProcess.NotRunning:
            self.status.setText('后台任务仍在运行，请等待完成后关闭');event.ignore();return
        self.play_timer.stop();self.timer.stop();super(FaceInverseWindow,self).closeEvent(event)
    def toggle_play(self):
        self.require_session()
        if self.play_timer.isActive():self.play_timer.stop()
        else:self.play_timer.start(max(10,round(1000/self.tracking['fps'])))
    def advance_frame(self):
        if self.base:self.frame.setValue((self.frame.value()+1)%len(self.base['frames']))
    def choose_file(self,field):
        path,_=QtWidgets.QFileDialog.getOpenFileName(self,'选择文件',field.text())
        if path:field.setText(path)
    def source_config(self):
        out=config.settings();out.update({key:field.text().strip() for key,field in self.fields.items()});out['allow_newer_scene']=self.allow_newer_scene.isChecked();return out
    def save_settings(self):session.save(ROOT/'project_paths.json',self.source_config());self.status.setText('路径设置已保存')
    def prepare_project(self):
        folder=Path(self.folder.text()).resolve();folder.mkdir(parents=True,exist_ok=True)
        if (folder/'session.json').exists():raise ValueError('已有项目，请打开它或使用新目录')
        cfg=self.source_config();session.save(folder/'source_config.json',cfg,False)
        self.pending_path=folder/'session.json'
        self.start_job(['-m','faceinverse.project','prepare',str(folder),self.video.text(),'--config',str(folder/'source_config.json'),'--start',str(self.start.value()),'--duration',str(self.duration.value())],folder)
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
        self.loading=True;self.frame.setRange(0,len(self.base['frames'])-1);self.slider.setRange(0,len(self.base['frames'])-1)
        self.suggestions.clear()
        for item in session.suggestions(self.tracking):self.suggestions.addItem(item['label']+' · '+str(item['frame']),item['frame'])
        self.loading=False;self.refresh_samples();self.goto_frame(self.frame.value());self.tabs.setCurrentIndex(1);self.status.setText('项目已打开：'+str(self.path))
    def require_session(self):
        if self.path is None:raise ValueError('请先打开项目')
        if self.job and self.job.state()!=QtCore.QProcess.NotRunning:raise ValueError('计算中不能更改样本，请等待完成')
    def goto_frame(self,value):
        if self.loading or self.path is None:return
        blocker=QtCore.QSignalBlocker(self.slider);self.slider.setValue(value);del blocker
        file=self.path.parent/'reference'/('%06d.jpg'%value)
        if file.is_file():self.image.setPixmap(QtGui.QPixmap(str(file)).scaled(760,330,QtCore.Qt.KeepAspectRatio,QtCore.Qt.SmoothTransformation))
        else:self.image.setText('参考帧缓存尚未生成，请点击“生成 / 更新参考缓存”')
        if self.sync.isChecked():
            try:cmds.currentTime(self.base['frames'][value])
            except Exception as exc:self.status.setText(str(exc))
    def pull_time(self):
        self.require_session();time=cmds.currentTime(query=True);index=min(range(len(self.base['frames'])),key=lambda i:abs(self.base['frames'][i]-time));self.frame.setValue(index);self.goto_frame(index)
    def selected_id(self):
        row=self.table.currentRow()
        if row<0:raise ValueError('请先选择样本')
        return self.table.item(row,0).data(QtCore.Qt.UserRole)
    def refresh_samples(self):
        if self.path is None:return
        self.data=session.load(self.path);self.table.setRowCount(len(self.data['samples']))
        for row,a in enumerate(self.data['samples']):
            for col,value in enumerate([a['frame'],a['label'],a['region'],a['mode'],'是' if a.get('enabled',True) else '否','是' if a.get('hard',True) else '否']):
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
