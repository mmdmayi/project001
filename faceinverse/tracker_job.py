"""External jobs for the independent tracker UI and Maya's source preview."""
import argparse,json
from pathlib import Path
from . import config,session,video_io

def run(mode,settings,folder):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    source=settings['source'];info=video_io.probe(source)
    session.save(folder/'video_info.json',info,False)
    if mode=='preview':
        import cv2
        frame=next(video_io.decoded_frames(source,settings.get('start',0.),pre_rotation=settings.get('pre_rotation',0),auto_orientation=settings.get('auto_orientation',True)))
        image=frame.pop('image');h,w=image.shape[:2]
        if w>960:image=cv2.resize(image,(960,round(h*960/w)))
        ok,image=cv2.imencode('.jpg',image)
        if not ok:raise ValueError('预览编码失败')
        (folder/'preview.jpg').write_bytes(image.tobytes())
        session.save(folder/'preview.json',frame,False);return
    from .tasks_video import track
    tracking=track(source,folder/'tracking.json',config.ROOT/'models/face_landmarker.task',settings.get('start',0.),settings.get('duration') or None,
        pre_rotation=settings.get('pre_rotation',0),auto_orientation=settings.get('auto_orientation',True))
    video_io.cache_frames(tracking,folder)
    session.save(folder/'tracker.json',dict(version='0.4.0',tracking='tracking.json',input_settings=settings),False)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['preview','track']);p.add_argument('settings');p.add_argument('folder');a=p.parse_args()
    run(a.mode,session.load(a.settings),a.folder)
