"""Project preparation / sample solving. Outputs are versioned and never replace a baseline."""
import argparse,base64,datetime,json,os,subprocess,sys,uuid
from pathlib import Path
from . import session,config
ROOT=config.ROOT


def invoke(executable,args,folder,label):
    env=dict(os.environ);env['PYTHONPATH']=str(ROOT);env['OPENBLAS_NUM_THREADS']='1';env['OMP_NUM_THREADS']='1';env['MPLCONFIGDIR']=str(folder/'cache'/'mpl')
    # mayapy's Windows launcher can mangle non-ASCII argv; transmit job location as ASCII base64.
    if len(args)>=3 and args[:2]==['-m','faceinverse.maya_worker']:
        env['FACEINVERSE_JOB_B64']=base64.b64encode(str(args[2]).encode('utf8')).decode('ascii')
        env['FACEINVERSE_ROOT_B64']=base64.b64encode(str(ROOT).encode('utf8')).decode('ascii')
        args=['-c',"import os,sys,base64,runpy;sys.path.insert(0,base64.b64decode(os.environ['FACEINVERSE_ROOT_B64']).decode('utf8'));runpy.run_module('faceinverse.maya_worker',run_name='__main__')"]
    # Embedded runtime uses ._pth; Maya is the only child that needs PYTHONPATH.
    with open(folder/(label+'.log'),'w',encoding='utf8') as log:
        result=subprocess.run([str(executable)]+[str(a) for a in args],cwd=str(ROOT),env=env,stdout=log,stderr=subprocess.STDOUT)
    if result.returncode:raise RuntimeError(label+' 失败，查看 '+str(folder/(label+'.log')))


def status(folder,state,stage,**extra):session.save(folder/'status.json',dict(state=state,stage=stage,**extra),False)


def cache_frames(tracking,folder):
    import cv2
    cache=folder/'reference';cache.mkdir(exist_ok=True)
    capture=cv2.VideoCapture(tracking['source'])
    try:
        if not capture.isOpened():raise ValueError('无法打开参考视频')
        first=tracking['frames'][0]['source_frame'];capture.set(cv2.CAP_PROP_POS_FRAMES,first)
        for i,row in enumerate(tracking['frames']):
            ok,image=capture.read()
            if not ok:raise ValueError('参考视频提前结束')
            h,w=image.shape[:2]
            if w>640:image=cv2.resize(image,(640,round(h*640/w)))
            if not cv2.imwrite(str(cache/('%06d.jpg'%i)),image):
                # imwrite may fail with Unicode filenames in some OpenCV builds.
                ok,encoded=cv2.imencode('.jpg',image)
                if not ok:raise ValueError('无法编码参考图')
                (cache/('%06d.jpg'%i)).write_bytes(encoded.tobytes())
    finally:capture.release()


def prepare(folder,video,source_config,start=0.,duration=15.):
    folder=Path(folder).resolve();folder.mkdir(parents=True,exist_ok=True)
    if (folder/'session.json').exists():raise ValueError('该目录已有项目，请打开原项目或选择新目录')
    if not Path(source_config.get('scene','')).is_file():raise ValueError('请选择已有角色场景')
    status(folder,'running','角色响应采样')
    try:
        job=folder/'calibrate_job.json';session.save(job,dict(mode='calibrate',config=source_config,output=str(folder/'calibration.json')),False)
        invoke(source_config['maya_python'],['-m','faceinverse.maya_worker',job],folder,'calibrate')
        status(folder,'running','离线视频追踪')
        from .tasks_video import track
        track(video,folder/'tracking.json',ROOT/'models'/'face_landmarker.task',start,duration if duration>0 else None)
        from .retarget import retarget
        tracking=session.load(folder/'tracking.json');cal=session.load(folder/'calibration.json')
        base=retarget(cal,tracking);session.save(folder/'baseline.json',base,False)
        audio=folder/'audio.wav'
        ffmpeg=config.ffmpeg_path(source_config)
        if ffmpeg:
            audio_args=[ffmpeg,'-y','-ss',str(start),'-i',str(video)]
            if duration>0:audio_args+=['-t',str(duration)]
            with open(folder/'audio.log','w',encoding='utf8') as log:
                subprocess.run(audio_args+['-vn','-ac','1','-ar','48000',str(audio)],stdout=log,stderr=subprocess.STDOUT)
        status(folder,'running','保存初始动画')
        session.save(folder/'baseline_job.json',dict(mode='bake',config=source_config,animation=str(folder/'baseline.json'),output=str(folder/'baseline.mb'),audio=str(audio) if audio.is_file() else ''),False)
        invoke(source_config['maya_python'],['-m','faceinverse.maya_worker',folder/'baseline_job.json'],folder,'baseline_bake')
        cache_frames(tracking,folder)
        session.create(folder/'session.json',folder/'calibration.json',folder/'tracking.json',folder/'baseline.json',source_config)
        status(folder,'complete','项目已就绪',session=str(folder/'session.json'),scene=str(folder/'baseline.mb'))
        return folder/'session.json'
    except Exception as exc:status(folder,'failed',str(exc));raise


def recalculate(path,bake=True):
    path=Path(path).resolve();folder=path.parent
    info,cal,tracking,base=session.inputs(path)
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S')+'_'+uuid.uuid4().hex[:6]
    run=folder/'runs'/stamp;run.mkdir(parents=True)
    status(folder,'running','按关键表情重新计算')
    try:
        from .pose_solver import solve_samples
        result=solve_samples(info,cal,tracking,base);session.save(run/'animation.json',result,False)
        session.save(run/'session_snapshot.json',info,False)
        if bake:
            status(folder,'running','烘焙新版本动画')
            session.save(run/'job.json',dict(mode='bake',config=info['config'],animation=str(run/'animation.json'),output=str(run/'animation.mb'),audio=str(folder/'audio.wav') if (folder/'audio.wav').is_file() else ''),False)
            invoke(info['config']['maya_python'],['-m','faceinverse.maya_worker',run/'job.json'],run,'bake')
        session.save(folder/'latest.json',dict(run=session.relative(run,folder),animation=session.relative(run/'animation.json',folder),
            scene=session.relative(run/'animation.mb',folder) if bake else None,report=result['key_expression_report']),False)
        status(folder,'complete','重算完成',run=str(run),scene=str(run/'animation.mb') if bake else '')
        return run
    except Exception as exc:status(folder,'failed',str(exc));raise


if __name__=='__main__':
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='command',required=True)
    a=sub.add_parser('prepare');a.add_argument('folder');a.add_argument('video');a.add_argument('--config',required=True);a.add_argument('--start',type=float,default=0.);a.add_argument('--duration',type=float,default=15.)
    a=sub.add_parser('solve');a.add_argument('session');a.add_argument('--no-bake',action='store_true')
    a=sub.add_parser('cache');a.add_argument('session')
    args=p.parse_args()
    if args.command=='prepare':prepare(args.folder,args.video,session.load(args.config),args.start,args.duration)
    elif args.command=='solve':print(recalculate(args.session,not args.no_bake))
    else:
        s,c,t,b=session.inputs(args.session);cache_frames(t,Path(args.session).resolve().parent)
