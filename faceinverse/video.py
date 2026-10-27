"""Optional offline MediaPipe baseline. Output is tracking data, NOT rig targets."""
import argparse
import json


def track(video, output):
    import cv2
    import mediapipe as mp
    capture = cv2.VideoCapture(video)
    if not capture.isOpened(): raise ValueError('Cannot open video')
    fps = capture.get(cv2.CAP_PROP_FPS)
    if fps <= 0: raise ValueError('Video has invalid FPS')
    rows=[]
    try:
        with mp.solutions.face_mesh.FaceMesh(static_image_mode=False,max_num_faces=1,
                                             refine_landmarks=True) as tracker:
            index=0
            while True:
                ok,frame=capture.read()
                if not ok: break
                result=tracker.process(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB))
                faces=result.multi_face_landmarks
                points=[[p.x,p.y,p.z] for p in faces[0].landmark] if faces else None
                rows.append(dict(frame=index,time_seconds=index/fps,detected=bool(faces),landmarks=points))
                index+=1
    finally:
        capture.release()
    if not rows: raise ValueError('No decoded frames')
    with open(output,'w',encoding='utf8') as f:
        json.dump(dict(schema=1,kind='mediapipe_normalized_tracking_NOT_rig_features',
                       fps=fps,frames=rows),f,allow_nan=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('video'); parser.add_argument('output')
    args=parser.parse_args(); track(args.video,args.output)
