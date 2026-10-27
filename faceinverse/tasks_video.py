"""Offline video expression tracking with official MediaPipe Tasks model."""
import argparse,json,os,time
from pathlib import Path

def track(source,output,model,start=0.,duration=None,max_width=960):
    import cv2
    import mediapipe as mp
    capture=cv2.VideoCapture(str(source))
    if not capture.isOpened():raise ValueError('Cannot decode '+str(source))
    fps=capture.get(cv2.CAP_PROP_FPS);width=int(capture.get(3));height=int(capture.get(4))
    if fps<=0:raise ValueError('Invalid video FPS')
    offset=round(start*fps);capture.set(cv2.CAP_PROP_POS_FRAMES,offset)
    limit=round(duration*fps) if duration is not None else None
    options=mp.tasks.vision.FaceLandmarkerOptions(base_options=mp.tasks.BaseOptions(model_asset_buffer=Path(model).read_bytes()),
        running_mode=mp.tasks.vision.RunningMode.VIDEO,num_faces=1,output_face_blendshapes=True,
        output_facial_transformation_matrixes=True)
    rows=[];started=time.perf_counter()
    try:
        with mp.tasks.vision.FaceLandmarker.create_from_options(options) as landmarker:
            i=0
            while limit is None or i<limit:
                ok,frame=capture.read()
                if not ok:break
                if width>max_width:frame=cv2.resize(frame,(max_width,round(height*max_width/width)))
                rgb=cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)
                result=landmarker.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB,data=rgb),round(i*1000/fps))
                detected=bool(result.face_landmarks)
                rows.append(dict(frame=i,source_frame=offset+i,time_seconds=i/fps,detected=detected,
                    landmarks=[[p.x,p.y,p.z] for p in result.face_landmarks[0]] if detected else None,
                    scores={c.category_name:float(c.score) for c in result.face_blendshapes[0]} if detected else None,
                    transform=result.facial_transformation_matrixes[0].tolist() if detected and result.facial_transformation_matrixes else None))
                i+=1
    finally:capture.release()
    if not rows:raise ValueError('No decoded frames')
    data=dict(schema=2,kind='mediapipe_tasks_expression_tracking',source=str(Path(source).resolve()),fps=fps,width=width,height=height,
        source_start_seconds=start,frames=rows,seconds=time.perf_counter()-started,model=str(Path(model).resolve()))
    Path(output).parent.mkdir(parents=True,exist_ok=True)
    Path(output).write_text(json.dumps(data,allow_nan=False),encoding='utf8')
    print(json.dumps(dict(output=str(output),frames=len(rows),detected=sum(r['detected'] for r in rows),seconds=data['seconds'])),flush=True)
    return data

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source');p.add_argument('output');p.add_argument('--model',default='models/face_landmarker.task')
    p.add_argument('--start',type=float,default=0.);p.add_argument('--duration',type=float);a=p.parse_args()
    os.environ.setdefault('MPLCONFIGDIR',str(Path('work/mpl').resolve()))
    track(a.source,a.output,a.model,a.start,a.duration)
