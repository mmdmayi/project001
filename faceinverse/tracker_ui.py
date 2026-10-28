"""Independent tracker workbench; PySide2 from the selected Maya, inference external."""
import bisect,datetime,json,sys,uuid,os
from pathlib import Path
from PySide2 import QtCore,QtGui,QtWidgets
from . import config,session
from .tracking_view import FrameCanvas,SignalPlot,DARK_STYLE

class TrackerWindow(QtWidgets.QDialog):
    probed=QtCore.Signal(dict)
    def __init__(self):
        super(TrackerWindow,self).__init__();self.setWindowTitle('FaceInverse 0.4 · Tracker');self.setFont(QtGui.QFont('Microsoft YaHei',10));self.resize(1200,880)
        self.setStyleSheet(DARK_STYLE)
        self.tracking=None;self.folder=None;self.job=None;self.dirty=False;self.review={}
        layout=QtWidgets.QVBoxLayout(self);top=QtWidgets.QHBoxLayout();self.source=QtWidgets.QLineEdit();top.addWidget(self.source)
        top.addWidget(self.button('选择视频',self.choose_video));top.addWidget(self.button('打开追踪结果',self.open_result));layout.addLayout(top)
        row=QtWidgets.QHBoxLayout();row.addWidget(QtWidgets.QLabel('追踪前顺时针旋转'));self.pre_rotation=QtWidgets.QComboBox()
        for a in (0,90,180,270):self.pre_rotation.addItem(str(a)+'°',a)
        row.addWidget(self.pre_rotation);self.auto=QtWidgets.QCheckBox('读取视频方向元数据');self.auto.setChecked(True);row.addWidget(self.auto)
        row.addWidget(QtWidgets.QLabel('起点/秒'));self.start=QtWidgets.QDoubleSpinBox();self.start.setRange(0,86400);row.addWidget(self.start)
        row.addWidget(QtWidgets.QLabel('时长/秒（0=全部）'));self.duration=QtWidgets.QDoubleSpinBox();self.duration.setRange(0,86400);row.addWidget(self.duration)
        row.addWidget(self.button('读取 / 预览',self.preview));row.addWidget(self.button('自动追踪 · 新版本',self.track));layout.addLayout(row)
        self.info=QtWidgets.QLabel('先把输入画面转正，再追踪。修改输入旋转必须重新追踪。');self.info.setWordWrap(True);layout.addWidget(self.info)
        split=QtWidgets.QSplitter();self.canvas=FrameCanvas();split.addWidget(self.canvas)
        right=QtWidgets.QWidget();box=QtWidgets.QVBoxLayout(right);self.candidates=QtWidgets.QListWidget();self.candidates.setWordWrap(True);box.addWidget(QtWidgets.QLabel('动作候选 · 需人工确认'));box.addWidget(self.candidates)
        self.scores=QtWidgets.QPlainTextEdit();self.scores.setReadOnly(True);box.addWidget(self.scores);split.addWidget(right);split.setSizes([850,300]);layout.addWidget(split,1)
        row=QtWidgets.QHBoxLayout();self.region=QtWidgets.QComboBox()
        for title,key in [('全脸','all'),('眉毛','brows'),('眼睛','eyes'),('嘴','mouth')]:self.region.addItem(title,key)
        row.addWidget(self.region);self.overlay=QtWidgets.QCheckBox('追踪点');self.overlay.setChecked(True);row.addWidget(self.overlay)
        self.crop=QtWidgets.QCheckBox('放大所选区域');row.addWidget(self.crop);self.dense=QtWidgets.QCheckBox('全部478点');row.addWidget(self.dense)
        self.mark=QtWidgets.QComboBox();self.mark.addItems(['未检查','通过目视检查','需要修正']);row.addWidget(self.mark);row.addWidget(self.button('保存此帧检查标记',self.save_mark));layout.addLayout(row)
        row=QtWidgets.QHBoxLayout();row.addWidget(self.button('播放 / 暂停',self.play));self.frame=QtWidgets.QSpinBox();row.addWidget(self.frame)
        self.slider=QtWidgets.QSlider(QtCore.Qt.Horizontal);row.addWidget(self.slider,1);self.time_label=QtWidgets.QLabel();row.addWidget(self.time_label);layout.addLayout(row)
        self.plot=SignalPlot();layout.addWidget(self.plot);self.log=QtWidgets.QPlainTextEdit();self.log.setMaximumHeight(90);self.log.setReadOnly(True);layout.addWidget(self.log)
        self.frame.valueChanged.connect(self.goto);self.slider.valueChanged.connect(self.frame.setValue)
        self.candidates.itemDoubleClicked.connect(lambda item:self.frame.setValue(item.data(QtCore.Qt.UserRole)))
        for widget in (self.region,self.overlay,self.crop,self.dense):
            (widget.currentIndexChanged if isinstance(widget,QtWidgets.QComboBox) else widget.toggled).connect(lambda *_:self.goto(self.frame.value()))
        self.pre_rotation.currentIndexChanged.connect(self.invalidate);self.auto.toggled.connect(self.invalidate);self.source.textChanged.connect(self.invalidate)
        self.timer=QtCore.QTimer(self);self.timer.setTimerType(QtCore.Qt.PreciseTimer);self.timer.timeout.connect(self.advance);self.clock=QtCore.QElapsedTimer()
    def button(self,text,callback):
        button=QtWidgets.QPushButton(text);button.clicked.connect(lambda *_:self.safe(callback));return button
    def safe(self,callback):
        try:return callback()
        except Exception as exc:self.info.setText(str(exc));self.log.appendPlainText(str(exc))
    def invalidate(self,*_):
        self.dirty=True
        if hasattr(self,'timer'):self.timer.stop()
        self.canvas.setText('输入设置已修改；读取预览或重新追踪。旧结果保留在原目录。')
        self.info.setText('当前输入方向尚未追踪；不能把旧点位套在新方向上。')
    def choose_video(self):
        path,_=QtWidgets.QFileDialog.getOpenFileName(self,'选择视频')
        if path:self.source.setText(path);self.preview()
    def input_settings(self):return dict(source=self.source.text(),pre_rotation=self.pre_rotation.currentData(),auto_orientation=self.auto.isChecked(),start=self.start.value(),duration=self.duration.value())
    def new_folder(self,prefix):return config.ROOT/'projects'/'tracker'/('%s_%s_%s'%(prefix,datetime.datetime.now().strftime('%Y%m%d_%H%M%S'),uuid.uuid4().hex[:6]))
    def preview(self):self.start_job('preview',self.new_folder('preview'))
    def track(self):self.start_job('track',self.new_folder('track'))
    def start_job(self,mode,folder):
        if self.job and self.job.state()!=QtCore.QProcess.NotRunning:raise ValueError('后台任务仍在运行')
        if not Path(self.source.text()).is_file():raise ValueError('请选择视频')
        self.timer.stop();folder.mkdir(parents=True);session.save(folder/'input.json',self.input_settings(),False)
        self.job=QtCore.QProcess(self);self.job.setProgram(config.python_executable(True));self.job.setArguments(['-m','faceinverse.tracker_job',mode,str(folder/'input.json'),str(folder)]);self.job.setWorkingDirectory(str(config.ROOT))
        env=QtCore.QProcessEnvironment.systemEnvironment();env.remove('PYTHONHOME');env.insert('PYTHONPATH',str(config.ROOT));env.insert('OPENBLAS_NUM_THREADS','1');env.insert('MPLCONFIGDIR',str(folder/'mpl'));self.job.setProcessEnvironment(env)
        self.job.setProcessChannelMode(QtCore.QProcess.MergedChannels);self.job.readyReadStandardOutput.connect(lambda:self.log.appendPlainText(bytes(self.job.readAllStandardOutput()).decode('utf8',errors='replace')))
        self.job.finished.connect(lambda code,*_:self.finished(code,mode,folder));self.job.start();self.info.setText('正在处理；输出新版本 '+str(folder))
    def finished(self,code,mode,folder):
        if code:self.info.setText('处理失败，请看日志；未覆盖旧结果');return
        info=session.load(folder/'video_info.json')
        self.probed.emit(info)
        if mode=='track':self.load_tracking(folder/'tracking.json')
        else:
            self.dirty=True;self.canvas.set_frame(folder/'preview.jpg');self.info.setText('预览：%s fps · 存储 %s×%s · 元数据方向 %s°；此时尚未追踪'%(info['fps'],info['storage_width'],info['storage_height'],info['metadata_rotation_cw']))
    def open_result(self):
        path,_=QtWidgets.QFileDialog.getOpenFileName(self,'选择 tracking.json / tracker.json / session.json',str(config.ROOT/'projects'),'JSON (*.json)')
        if path:self.load_tracking(path)
    def load_tracking(self,path):
        path=Path(path);data=session.load(path)
        if path.name=='session.json':path=session.resolve(path,data['paths']['tracking']);data=session.load(path)
        elif path.name=='tracker.json':path=path.parent/data['tracking'];data=session.load(path)
        self.tracking=data;self.folder=path.parent;self.dirty=False
        self.source.blockSignals(True);self.source.setText(data['source']);self.source.blockSignals(False)
        for widget in (self.pre_rotation,self.auto):widget.blockSignals(True)
        self.pre_rotation.setCurrentIndex(self.pre_rotation.findData(data.get('requested_rotation_cw',0)));self.auto.setChecked(data.get('auto_orientation',True))
        for widget in (self.pre_rotation,self.auto):widget.blockSignals(False)
        self.frame.setRange(0,len(data['frames'])-1);self.slider.setRange(0,len(data['frames'])-1);self.plot.rows=data['frames']
        self.review=session.load(self.folder/'tracking_review.json') if (self.folder/'tracking_review.json').exists() else {}
        self.candidates.clear()
        for row in session.suggestions(data):
            item=QtWidgets.QListWidgetItem('%s\n源采样帧%d · 系数%.3f'%(row['label'],row['frame'],row['score']));item.setToolTip(row.get('evidence','')+'；需看视频确认，系数不是置信度');item.setData(QtCore.Qt.UserRole,row['frame']);self.candidates.addItem(item)
        self.info.setText('追踪 %d 帧 / 检出 %d · %g fps · 追踪前旋转 %s° · %s'%(len(data['frames']),sum(bool(f['detected']) for f in data['frames']),data['fps'],data.get('preprocess_rotation_cw',0),data.get('timebase','旧版标称时间')))
        self.goto(0)
    def goto(self,index):
        if not self.tracking or self.dirty:return
        row=self.tracking['frames'][index];block=QtCore.QSignalBlocker(self.slider);self.slider.setValue(index);del block
        self.canvas.region=self.region.currentData();self.canvas.overlay=self.overlay.isChecked();self.canvas.crop=self.crop.isChecked();self.canvas.dense=self.dense.isChecked()
        self.canvas.set_frame(self.folder/'reference'/('%06d.jpg'%index),row)
        self.time_label.setText('源帧 %s · %.3f 秒'%(row.get('source_frame',index),row['time_seconds']))
        self.scores.setPlainText('\n'.join('%s: %.4f'%(k,v) for k,v in sorted((row.get('scores') or {}).items(),key=lambda pair:-pair[1]) if not k.startswith('_')))
        self.mark.setCurrentIndex(int(self.review.get(str(index),0)));self.plot.current=index;self.plot.update()
    def save_mark(self):
        if not self.tracking or self.dirty:raise ValueError('请先打开有效追踪结果')
        self.review[str(self.frame.value())]=self.mark.currentIndex();session.save(self.folder/'tracking_review.json',self.review)
    def play(self):
        if self.timer.isActive():self.timer.stop();return
        if not self.tracking or self.dirty:raise ValueError('请先追踪或打开结果')
        self.origin=self.tracking['frames'][self.frame.value()]['time_seconds'];self.clock.start();self.timer.start(8)
    def advance(self):
        times=[r['time_seconds'] for r in self.tracking['frames']];t=self.origin+self.clock.elapsed()/1000.
        index=min(len(times)-1,max(0,bisect.bisect_right(times,t)-1));self.frame.setValue(index)
        if t>=times[-1]:self.timer.stop()
    def closeEvent(self,event):
        if self.job and self.job.state()!=QtCore.QProcess.NotRunning:self.info.setText('后台处理中，请完成后关闭');event.ignore();return
        self.timer.stop();event.accept()

if __name__=='__main__':
    app=QtWidgets.QApplication.instance() or QtWidgets.QApplication([]);window=TrackerWindow();window.show()
    if os.environ.get('FACEINVERSE_TRACKER_SMOKE')=='1':
        def smoke():
            session.save(config.ROOT/'work/tracker_smoke.json',dict(passed=True,root=str(config.ROOT),python=sys.version,
                qt=QtCore.__version__,standalone_maya_initialized='maya.standalone' in sys.modules),False)
            window.close();app.quit()
        QtCore.QTimer.singleShot(500,smoke)
    sys.exit(app.exec_())
