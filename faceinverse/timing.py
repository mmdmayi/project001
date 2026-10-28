"""Time mapping shared by Maya Python 3.7 and the external runtime."""
import math

def valid_fps(value):
    fps=float(value)
    if not math.isfinite(fps) or not 1<=fps<=240:raise ValueError('帧率必须在 1–240 之间')
    return fps

def frames_from_times(times,fps,start_frame=1.):
    fps=valid_fps(fps);start=float(start_frame)
    if not math.isfinite(start):raise ValueError('起始帧无效')
    result=[start+fps*float(t) for t in times]
    if not all(math.isfinite(x) for x in result) or any(b<=a for a,b in zip(result,result[1:])):raise ValueError('时间戳必须严格递增')
    return result

def maya_unit(fps):
    fps=scene_rate(fps)
    for numerator,label in ((24000,'23.976fps'),(30000,'29.97fps'),(60000,'59.94fps')):
        if abs(fps-numerator/1001.)<1e-6:return label
    for value,name in ((24,'film'),(25,'pal'),(30,'ntsc'),(48,'show'),(50,'palf'),(60,'ntscf')):
        if abs(fps-value)<1e-8:return name
    return ('%.12g'%fps)+'fps'

def scene_rate(fps):
    fps=valid_fps(fps)
    for numerator,nominal in ((24000,23.976),(30000,29.97),(60000,59.94)):
        if abs(fps-nominal)<.0001:return numerator/1001.
    if fps not in (12,15,24,25,30,48,50,60,100,120,240):raise ValueError('此帧率不是本版已验证的 Maya 原生时间单位。请选择24/25/30/50/60，NTSC 23.976/29.97/59.94，或100/120/240；视频按秒对齐。')
    return fps

def automatic_scene_rate(source_fps):
    value=valid_fps(source_fps)
    try:return scene_rate(value)
    except ValueError:
        native=[12,15,24,25,30,48,50,60,100,120,240,24000/1001.,30000/1001.,60000/1001.]
        return min(native,key=lambda fps:abs(fps-value))

def rotation(value):
    angle=int(value)
    if float(value)!=angle or angle%90:raise ValueError('旋转角度须为 0/90/180/270 度')
    return angle%360

def rotate_xy(x,y,angle):
    angle=rotation(angle)
    return {0:(x,y),90:(1-y,x),180:(1-x,1-y),270:(y,1-x)}[angle]
