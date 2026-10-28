"""Shared PySide2 video/landmark widgets; no Maya or scientific imports."""
import math
from PySide2 import QtCore,QtGui,QtWidgets

REGIONS={
    'brows':[[70,63,105,66,107],[336,296,334,293,300]],
    'eyes':[[33,160,158,133,153,144,33],[362,385,387,263,373,380,362]],
    'mouth':[[61,40,37,0,267,270,291,321,314,17,84,91,61],[78,81,13,311,308,402,14,178,78]]}
COLORS={'brows':'#ffbf69','eyes':'#55d6c2','mouth':'#f87699'}
DARK_STYLE='QDialog,QWidget {background:#242b36;color:#e4eaf3;} QLineEdit,QPlainTextEdit,QListWidget,QTableWidget,QComboBox,QSpinBox,QDoubleSpinBox {background:#171e29;color:#e4eaf3;border:1px solid #445167;border-radius:3px;padding:3px;} QPushButton {background:#35445a;border:1px solid #586b85;border-radius:4px;padding:6px;} QPushButton:hover {background:#426083;} QHeaderView::section {background:#35445a;padding:4px;} QTabBar::tab {padding:7px;background:#303d50;} QTabBar::tab:selected {background:#426083;} QToolTip {background:#f1f3f5;color:#151a22;}'

class FrameCanvas(QtWidgets.QWidget):
    def __init__(self,parent=None):
        super(FrameCanvas,self).__init__(parent);self.pixmap=QtGui.QPixmap();self.row={};self.angle=0
        self.region='all';self.overlay=True;self.crop=False;self.dense=False;self.message='打开视频 / 项目以显示参考画面'
        self.setMinimumSize(280,200);self.setSizePolicy(QtWidgets.QSizePolicy.Expanding,QtWidgets.QSizePolicy.Expanding)
    def set_frame(self,path,row=None,angle=0):
        self.pixmap=QtGui.QPixmap(str(path)) if path else QtGui.QPixmap();self.row=row or {};self.angle=int(angle)%360;self.update()
    def setText(self,text):self.message=text;self.pixmap=QtGui.QPixmap();self.update()
    def paintEvent(self,event):
        painter=QtGui.QPainter(self);painter.fillRect(self.rect(),QtGui.QColor('#151a22'))
        if self.pixmap.isNull():
            painter.setPen(QtGui.QColor('#b7c6d8'));painter.drawText(self.rect(),QtCore.Qt.AlignCenter,self.message);return
        pix=QtGui.QPixmap(self.pixmap);w,h=pix.width(),pix.height();points=self.row.get('landmarks') or []
        ids=[]
        if points:
            p=QtGui.QPainter(pix);p.setRenderHint(QtGui.QPainter.Antialiasing)
            for region,chains in REGIONS.items():
                if self.region not in ('all',region):continue
                for chain in chains:
                    ids.extend(chain)
                    if self.overlay:
                        p.setPen(QtGui.QPen(QtGui.QColor(COLORS[region]),max(1.1,w/650.)))
                        polygon=QtGui.QPolygonF([QtCore.QPointF(points[i][0]*w,points[i][1]*h) for i in chain if i<len(points)])
                        p.drawPolyline(polygon)
                        for xy in polygon:p.drawEllipse(xy,2.3,2.3)
            if self.overlay and self.dense:
                p.setPen(QtGui.QColor('#97a6c1'))
                for xyz in points:p.drawPoint(QtCore.QPointF(xyz[0]*w,xyz[1]*h))
            p.end()
        if self.crop and self.region!='all' and ids:
            xs=[points[i][0]*w for i in ids];ys=[points[i][1]*h for i in ids];margin=max(max(xs)-min(xs),max(ys)-min(ys))*.35
            box=QtCore.QRectF(min(xs)-margin,min(ys)-margin,max(xs)-min(xs)+2*margin,max(ys)-min(ys)+2*margin).toAlignedRect().intersected(pix.rect())
            if box.width()>5 and box.height()>5:pix=pix.copy(box)
        if self.angle:pix=pix.transformed(QtGui.QTransform().rotate(self.angle),QtCore.Qt.SmoothTransformation)
        pix=pix.scaled(self.size(),QtCore.Qt.KeepAspectRatio,QtCore.Qt.SmoothTransformation)
        painter.drawPixmap((self.width()-pix.width())//2,(self.height()-pix.height())//2,pix)
        painter.setPen(QtGui.QColor('#6fe1bb' if self.row.get('detected') else '#f8c370'))
        painter.drawText(12,22,'已检出面部' if self.row.get('detected') else '预览 / 未检出（不可作为可靠样本）')

class SignalPlot(QtWidgets.QWidget):
    def __init__(self,parent=None):
        super(SignalPlot,self).__init__(parent);self.rows=[];self.current=0;self.keys=['jawOpen','mouthSmileLeft','eyeBlinkLeft'];self.setMinimumHeight(90)
    def paintEvent(self,event):
        p=QtGui.QPainter(self);p.fillRect(self.rect(),QtGui.QColor('#1b2230'))
        if not self.rows:return
        width=max(1,self.width()-20);height=max(1,self.height()-28);n=len(self.rows)
        for key,color in zip(self.keys,['#f87699','#55d6c2','#ffbf69']):
            p.setPen(QtGui.QPen(QtGui.QColor(color),1.2));line=QtGui.QPolygonF()
            # Draw at most one sample per horizontal pixel, not an unbounded per-frame polygon.
            step=max(1,n//max(1,width))
            for i in range(0,n,step):
                value=(self.rows[i].get('scores') or {}).get(key,0.)
                line.append(QtCore.QPointF(10+width*i/max(1,n-1),10+height*(1-min(1,max(0,value)))))
            p.drawPolyline(line)
        p.setPen(QtGui.QColor('#e5eaf3'));x=10+width*self.current/max(1,n-1);p.drawLine(QtCore.QPointF(x,5),QtCore.QPointF(x,self.height()-15))
        for i,row in enumerate(self.rows):
            if not row.get('detected'):
                p.setPen(QtGui.QColor('#f06464'));p.drawPoint(QtCore.QPointF(10+width*i/max(1,n-1),self.height()-8))
        p.setPen(QtGui.QColor('#c5d1e3'));p.drawText(12,self.height()-3,'jawOpen / mouthSmileLeft / eyeBlinkLeft · 模型系数，非 FACS 真值')
