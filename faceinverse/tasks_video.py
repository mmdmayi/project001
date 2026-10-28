"""Offline tracking; rotate BEFORE inference and retain decoded timestamps."""
import argparse,json,os,time
from pathlib import Path
from . import video_io

def track(source,output,model,start=0.,duration=None,max_width=960,pre_rotation=0,auto_orientation=True):
    import cv2
    import mediapipe as mp
    info=video_io.probe(source)
    options=mp.tasks.vision.FaceLandmarkerOptions(base_options=mp.tasks.BaseOptions(model_asset_buffer=Path(model).read_bytes()),
        running_mode=mp.tasks.vision.RunningMode.VIDEO,num_faces=1,output_face_blendshapes=True,output_facial_transformation_matrixes=True)
    rows=[];started=time.perf_counter();last_ms=-1
    with mp.tasks.vision.FaceLandmarker.create_from_options(options) as landmarker:
        for frame in video_io.decoded_frames(source,start,duration,pre_rotation,auto_orientation):
            image=frame.pop('image');height,width=image.shape[:2]
            if width>max_width:image=cv2.resize(image,(max_width,round(height*max_width/width)))
            timestamp=max(last_ms+1,round(frame['time_seconds']*1000));last_ms=timestamp
            result=landmarker.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB,data=cv2.cvtColor(image,cv2.COLOR_BGR2RGB)),timestamp)
            detected=bool(result.face_landmarks)
            rows.append(dict(frame=len(rows),**frame,detected=detected,
                landmarks=[[p.x,p.y,p.z] for p in result.face_landmarks[0]] if detected else None,
                scores={c.category_name:float(c.score) for c in result.face_blendshapes[0]} if detected else None,
                transform=result.facial_transformation_matrixes[0].tolist() if detected and result.facial_transformation_matrixes else None))
    if not rows:raise ValueError('没有解码帧')
    data=dict(schema=3,kind='mediapipe_tasks_expression_tracking',source=info['source'],fps=info['fps'],width=width,height=height,
        source_start_seconds=rows[0]['source_time_seconds'],requested_start_seconds=start,
        frames=rows,seconds=time.perf_counter()-started,model=str(Path(model).resolve()),
        preprocess_rotation_cw=rows[0]['preprocess_rotation_cw'],requested_rotation_cw=pre_rotation,
        auto_orientation=bool(auto_orientation),timebase=rows[-1]['timebase'],video_info=info,
        source_file_stat=dict(size=Path(source).stat().st_size,mtime_ns=Path(source).stat().st_mtime_ns))
    Path(output).parent.mkdir(parents=True,exist_ok=True);Path(output).write_text(json.dumps(data,allow_nan=False),encoding='utf8')
    print(json.dumps(dict(output=str(output),frames=len(rows),detected=sum(r['detected'] for r in rows),seconds=data['seconds'],fps=data['fps'],timebase=data['timebase'])),flush=True)
    return data

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source');p.add_argument('output');p.add_argument('--model',default='models/face_landmarker.task')
    p.add_argument('--start',type=float,default=0.);p.add_argument('--duration',type=float);p.add_argument('--rotation',type=int,default=0);p.add_argument('--no-auto-orientation',action='store_true');a=p.parse_args()
    track(a.source,a.output,a.model,a.start,a.duration,pre_rotation=a.rotation,auto_orientation=not a.no_auto_orientation)
