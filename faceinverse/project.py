"""Project preparation / sample solving. Outputs are versioned and never replace a baseline."""
import argparse,base64,datetime,json,os,subprocess,sys,uuid,copy,shutil
from pathlib import Path
from . import session,config
ROOT=config.ROOT


def invoke(executable,args,folder,label):
    env=dict(os.environ);env['PYTHONPATH']=str(ROOT);env['OPENBLAS_NUM_THREADS']='1';env['OMP_NUM_THREADS']='1';env['MPLCONFIGDIR']=str(folder/'cache'/'mpl')
    # mayapy's Windows launcher can mangle non-ASCII argv; transmit job location as ASCII base64.
    if len(args)>=3 and args[:2]==['-m','faceinverse.maya_worker']:
        env.pop('PYTHONHOME',None);env['MAYA_PYTHON_VERSION']='3'
        env['FACEINVERSE_JOB_B64']=base64.b64encode(str(args[2]).encode('utf8')).decode('ascii')
        env['FACEINVERSE_ROOT_B64']=base64.b64encode(str(ROOT).encode('utf8')).decode('ascii')
        args=['-c',"import os,sys,base64,runpy;sys.path.insert(0,base64.b64decode(os.environ['FACEINVERSE_ROOT_B64']).decode('utf8'));runpy.run_module('faceinverse.maya_worker',run_name='__main__')"]
    # Embedded runtime uses ._pth; Maya is the only child that needs PYTHONPATH.
    with open(folder/(label+'.log'),'w',encoding='utf8') as log:
        result=subprocess.run([str(executable)]+[str(a) for a in args],cwd=str(ROOT),env=env,stdout=log,stderr=subprocess.STDOUT)
    if result.returncode:raise RuntimeError(label+' 失败，查看 '+str(folder/(label+'.log')))


def status(folder,state,stage,**extra):session.save(folder/'status.json',dict(state=state,stage=stage,**extra),False)


def cache_frames(tracking,folder):
    from .video_io import cache_frames as cache
    return cache(tracking,folder)


def prepare(folder,video,source_config,start=0.,duration=15.):
    folder=Path(folder).resolve();folder.mkdir(parents=True,exist_ok=True)
    if (folder/'session.json').exists():raise ValueError('该目录已有项目，请打开原项目或选择新目录')
    if not Path(source_config.get('scene','')).is_file():raise ValueError('请选择已有角色场景')
    from .timing import scene_rate,automatic_scene_rate
    from .video_io import probe
    fps=scene_rate(source_config['output_fps']) if source_config.get('output_fps') else automatic_scene_rate(probe(video)['fps'])
    status(folder,'running','角色响应采样')
    try:
        job=folder/'calibrate_job.json';session.save(job,dict(mode='calibrate',config=source_config,output=str(folder/'calibration.json')),False)
        invoke(source_config['maya_python'],['-m','faceinverse.maya_worker',job],folder,'calibrate')
        status(folder,'running','离线视频追踪')
        from .tasks_video import track
        cached=source_config.get('tracking_cache')
        if cached:
            cached=Path(cached);data=session.load(cached);source=Path(video).resolve();stat=source.stat()
            if Path(data['source']).resolve()!=source or data.get('source_file_stat')!=dict(size=stat.st_size,mtime_ns=stat.st_mtime_ns):raise ValueError('追踪缓存的源视频路径或文件状态已变化，请重新追踪')
            from .timing import rotation
            metadata=probe(source)['metadata_rotation_cw'] if source_config.get('auto_orientation',True) else 0
            if rotation(metadata+source_config.get('pre_rotation',0))!=data.get('preprocess_rotation_cw'):raise ValueError('追踪前方向与缓存不同，必须重新追踪')
            session.save(folder/'tracking.json',data,False)
        else:
            track(video,folder/'tracking.json',ROOT/'models'/'face_landmarker.task',start,duration if duration>0 else None,
                  pre_rotation=source_config.get('pre_rotation',0),auto_orientation=source_config.get('auto_orientation',True))
        from .retarget import retarget
        tracking=session.load(folder/'tracking.json');cal=session.load(folder/'calibration.json')
        base=retarget(cal,tracking,scene_fps=fps,start_frame=source_config.get('start_frame',1.));session.save(folder/'baseline.json',base,False)
        audio=folder/'audio.wav'
        ffmpeg=config.ffmpeg_path(source_config)
        if ffmpeg:
            audio_args=[ffmpeg,'-y','-ss',str(tracking.get('source_start_seconds',start)),'-i',str(video)]
            if duration>0:audio_args+=['-t',str(duration)]
            with open(folder/'audio.log','w',encoding='utf8') as log:
                subprocess.run(audio_args+['-vn','-ac','1','-ar','48000',str(audio)],stdout=log,stderr=subprocess.STDOUT)
        status(folder,'running','保存初始动画')
        session.save(folder/'baseline_job.json',dict(mode='bake',config=source_config,animation=str(folder/'baseline.json'),output=str(folder/'baseline.mb'),audio=str(audio) if audio.is_file() else ''),False)
        invoke(source_config['maya_python'],['-m','faceinverse.maya_worker',folder/'baseline_job.json'],folder,'baseline_bake')
        if cached and (cached.parent/'reference').exists():shutil.copytree(cached.parent/'reference',folder/'reference')
        else:cache_frames(tracking,folder)
        session.create(folder/'session.json',folder/'calibration.json',folder/'tracking.json',folder/'baseline.json',source_config)
        status(folder,'complete','项目已就绪',session=str(folder/'session.json'),scene=str(folder/'baseline.mb'))
        return folder/'session.json'
    except Exception as exc:status(folder,'failed',str(exc));raise


def fork_settings(path,settings):
    """New project for a new time unit/channel set. Never mutates an old baseline."""
    from . import groups,timing
    path=Path(path).resolve();info,cal,tracking,base=session.inputs(path)
    destination=Path(settings['destination']).resolve()
    if destination.exists():raise ValueError('新版本目录已存在')
    updated=copy.deepcopy(base);wanted=settings.get('groups',groups.available(info,base['plugs']))
    groups.validate(wanted,cal)
    physical={c['plug']:c for c in cal['physical_controls']}
    extras=sorted({p for group in wanted.values() for p in group['plugs']}-set(base['plugs']))
    updated['plugs']+=extras
    updated['values']=[list(row)+[physical[p]['neutral'] for p in extras] for row in base['values']]
    fps=timing.scene_rate(settings.get('scene_fps') or base.get('scene_fps',24.));start=float(settings.get('start_frame',base['frames'][0]))
    updated.update(scene_fps=fps,start_frame=start,frames=timing.frames_from_times([r['time_seconds'] for r in tracking['frames']],fps,start))
    destination.mkdir(parents=True)
    for name,data in (('calibration.json',cal),('tracking.json',tracking),('baseline.json',updated)):session.save(destination/name,data,False)
    new=session.create(destination/'session.json',destination/'calibration.json',destination/'tracking.json',destination/'baseline.json',info['config'])
    new.update(groups=wanted,samples=copy.deepcopy(info['samples']),settings=copy.deepcopy(info.get('settings',{})),
               view=copy.deepcopy(info.get('view',{})),parent_session=str(path))
    session.save(destination/'session.json',new,False)
    if (path.parent/'reference').exists():shutil.copytree(path.parent/'reference',destination/'reference')
    if (path.parent/'audio.wav').exists():shutil.copy2(path.parent/'audio.wav',destination/'audio.wav')
    recalculate(destination/'session.json')
    return destination/'session.json'


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
    a=sub.add_parser('fork');a.add_argument('session');a.add_argument('--settings',required=True)
    args=p.parse_args()
    if args.command=='prepare':prepare(args.folder,args.video,session.load(args.config),args.start,args.duration)
    elif args.command=='solve':print(recalculate(args.session,not args.no_bake))
    elif args.command=='fork':print(fork_settings(args.session,session.load(args.settings)))
    else:
        s,c,t,b=session.inputs(args.session);cache_frames(t,Path(args.session).resolve().parent)
