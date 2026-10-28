"""External OpenCV decoder. Storage orientation, preprocessing and display stay distinct."""
import math
from pathlib import Path
from .timing import rotation,valid_fps

def capture_source(path):
    import cv2
    cap=cv2.VideoCapture(str(path))
    if not cap.isOpened():raise ValueError('无法打开视频: '+str(path))
    # Prevent an implicit second rotation inside OpenCV.
    if hasattr(cv2,'CAP_PROP_ORIENTATION_AUTO'):cap.set(cv2.CAP_PROP_ORIENTATION_AUTO,0)
    return cap

def rotate_image(image,angle):
    import cv2
    angle=rotation(angle)
    if angle==0:return image
    return cv2.rotate(image,{90:cv2.ROTATE_90_CLOCKWISE,180:cv2.ROTATE_180,270:cv2.ROTATE_90_COUNTERCLOCKWISE}[angle])

def probe(path):
    import cv2
    cap=capture_source(path)
    try:
        fps=valid_fps(cap.get(cv2.CAP_PROP_FPS));width=int(cap.get(3));height=int(cap.get(4))
        angle=cap.get(cv2.CAP_PROP_ORIENTATION_META) if hasattr(cv2,'CAP_PROP_ORIENTATION_META') else 0.
        angle=rotation(round(angle/90)*90) if math.isfinite(angle) else 0
        return dict(source=str(Path(path).resolve()),fps=fps,storage_width=width,storage_height=height,
            frame_count=int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),metadata_rotation_cw=angle,
            note='Frame times are read from decoded POS_MSEC; nominal FPS is a display/output default.')
    finally:cap.release()

def decoded_frames(path,start=0.,duration=None,pre_rotation=0,auto_orientation=True):
    import cv2
    info=probe(path);angle=(info['metadata_rotation_cw'] if auto_orientation else 0)+rotation(pre_rotation)
    cap=capture_source(path);origin=None;previous=None;timebase='decoded_pts';index=0
    if not math.isfinite(start) or start<0 or duration is not None and (not math.isfinite(duration) or duration<=0):raise ValueError('截取时间无效')
    try:
        while True:
            ok,image=cap.read()
            if not ok:break
            pts=cap.get(cv2.CAP_PROP_POS_MSEC)/1000.
            if index==1 and (not math.isfinite(pts) or pts<=0):timebase='nominal_cfr_fallback'
            if timebase=='nominal_cfr_fallback':pts=index/info['fps']
            if not math.isfinite(pts) or previous is not None and pts<=previous:raise ValueError('解码时间戳无效或倒退；请转为恒定帧率视频后重试')
            previous=pts
            if pts+1e-8>=start:
                if origin is None:origin=pts
                if duration is not None and pts-origin>=duration-1e-8:break
                yield dict(source_frame=index,source_time_seconds=pts,time_seconds=pts-origin,
                    timebase=timebase,preprocess_rotation_cw=rotation(angle),image=rotate_image(image,angle))
            index+=1
    finally:cap.release()

def cache_frames(tracking,folder,max_width=960):
    import cv2
    cache=Path(folder)/'reference';cache.mkdir(parents=True,exist_ok=True)
    rows=tracking['frames'];wanted={r['source_frame']:i for i,r in enumerate(rows)}
    cap=capture_source(tracking['source']);index=0;written=0
    angle=tracking.get('preprocess_rotation_cw')
    # 0.3 tracked storage frames without an explicit rotation contract. Never
    # reinterpret an old point stream by guessing a new metadata transform.
    if angle is None:angle=0
    try:
        while written<len(rows):
            ok,image=cap.read()
            if not ok:raise ValueError('参考视频提前结束')
            if index in wanted:
                image=rotate_image(image,angle);h,w=image.shape[:2]
                if w>max_width:image=cv2.resize(image,(max_width,round(h*max_width/w)))
                ok,encoded=cv2.imencode('.jpg',image)
                if not ok:raise ValueError('参考帧编码失败')
                (cache/('%06d.jpg'%wanted[index])).write_bytes(encoded.tobytes());written+=1
            index+=1
    finally:cap.release()
    return cache
