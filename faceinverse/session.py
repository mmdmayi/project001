"""Portable project / pose sample storage. Standard library only: safe inside Maya."""
import copy,datetime,hashlib,json,math,os,shutil,uuid
from pathlib import Path


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def save(path,data,backup=True):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    serialized=json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)
    if backup and path.is_file():
        stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%f')
        archive=path.parent/'history';archive.mkdir(exist_ok=True)
        shutil.copy2(path,archive/(path.stem+'_'+stamp+'.json'))
    temporary=path.with_name(path.name+'.tmp')
    temporary.write_text(serialized,encoding='utf8');os.replace(str(temporary),str(path))


def fingerprint(data):
    return hashlib.sha256(json.dumps(data,sort_keys=True,allow_nan=False).encode('utf8')).hexdigest()


def rig_signature(calibration):
    return fingerprint(dict(controls=[{k:c[k] for k in ('plug','min','max','neutral')} for c in calibration['physical_controls']],
                            observations=calibration['observation_names']))


def resolve(session_path,value):
    path=Path(value)
    return path if path.is_absolute() else (Path(session_path).parent/path).resolve()


def relative(path,parent):
    try:return os.path.relpath(str(Path(path).resolve()),str(Path(parent).resolve())).replace('\\','/')
    except ValueError:return str(Path(path).resolve())


def descriptor(frame,score_names,width=1,height=1):
    if not frame.get('detected') or not frame.get('scores'):raise ValueError('该视频帧没有有效面部检测，不能作为表情样本')
    values=[float(frame['scores'].get(n,0.)) for n in score_names]
    if not all(math.isfinite(v) for v in values):raise ValueError('视频表情系数含非法数值')
    p=frame.get('landmarks');geometry=[0.]*5
    if p is not None and len(p)>386:
        def point(i):return (float(p[i][0])*width,float(p[i][1])*height)
        def sub(a,b):return (a[0]-b[0],a[1]-b[1])
        def norm(a):return math.hypot(a[0],a[1])
        def dot(a,b):return a[0]*b[0]+a[1]*b[1]
        horizontal=sub(point(263),point(33));span=norm(horizontal)
        if span>1e-8:
            down=(-horizontal[1]/span,horizontal[0]/span)
            if down[1]<0:down=(-down[0],-down[1])
            a,b=point(13),point(14);mid=((a[0]+b[0])/2,(a[1]+b[1])/2)
            geometry=[abs(dot(sub(b,a),down))/span,
                abs(dot(sub(point(374),point(386)),down))/max(norm(sub(point(263),point(362))),1e-8),
                abs(dot(sub(point(145),point(159)),down))/max(norm(sub(point(133),point(33))),1e-8),
                dot(sub(mid,point(291)),down)/span,dot(sub(mid,point(61)),down)/span]
    if not all(math.isfinite(v) for v in geometry):raise ValueError('视频几何比例含非法数值')
    return values+geometry


def create(path,calibration_path,tracking_path,baseline_path,config):
    path=Path(path).resolve();cal=load(calibration_path);tracking=load(tracking_path);baseline=load(baseline_path)
    if len(tracking['frames'])!=len(baseline['frames']):raise ValueError('追踪和基线动画帧数不同')
    names=sorted({n for f in tracking['frames'] if f.get('scores') for n in f['scores'] if not n.startswith('_')})
    if not names:raise ValueError('没有可用表情系数')
    info=dict(schema=1,version='0.3.1',session_id=str(uuid.uuid4()),
        rig_signature=rig_signature(cal),clip_id=fingerprint(dict(source=tracking.get('source'),start=tracking.get('source_start_seconds'),
             fps=tracking['fps'],frames=len(tracking['frames']),scores=[f.get('scores') for f in tracking['frames']])),
        paths=dict(calibration=relative(calibration_path,path.parent),tracking=relative(tracking_path,path.parent),
                   baseline=relative(baseline_path,path.parent)),
        baseline_hash=fingerprint(baseline),config=copy.deepcopy(config),score_names=names,samples=[],
        settings=dict(radius=2.,smoothing=.12),revision=0)
    save(path,info);return info


def inputs(path):
    s=load(path)
    if s.get('schema')!=1:raise ValueError('不支持的项目格式')
    cal=load(resolve(path,s['paths']['calibration']));tracking=load(resolve(path,s['paths']['tracking']));base=load(resolve(path,s['paths']['baseline']))
    if rig_signature(cal)!=s['rig_signature']:raise ValueError('角色标定签名已变化，请重新建立项目或恢复原标定')
    if fingerprint(base)!=s['baseline_hash']:raise ValueError('原始基线动画已变化；不能继续用旧样本静默覆盖，请恢复基线或新建项目')
    return s,cal,tracking,base


def channel_region(plug):
    name=plug.split('|')[-1].lower()
    if 'brow' in name:return 'brows'
    if 'eye' in name:return 'eyes'
    if 'jaw' in name:return 'jaw'
    if 'mouth' in name or 'nose' in name:return 'mouth'
    return 'other'


def choose_channels(plugs,region='all',selected=None):
    if region=='selected':
        nodes=set(selected or [])
        out=[p for p in plugs if p in nodes or p.rsplit('.',1)[0] in nodes]
    else:out=[p for p in plugs if region=='all' or channel_region(p)==region]
    if not out:raise ValueError('选定范围没有可用控制器')
    return out


def capture(path,frame,values,label='',region='all',mode='pose',hard=True,radius=2.,time_radius=.5,sample_id=None,mesh_snapshot=None):
    s,cal,tracking,base=inputs(path)
    if mode not in ('pose','local'):raise ValueError('样本模式无效')
    if not isinstance(frame,int) or not 0<=frame<len(tracking['frames']):raise ValueError('视频帧编号越界')
    if not math.isfinite(radius) or radius<=0 or not math.isfinite(time_radius) or time_radius<=0:raise ValueError('影响范围必须大于零')
    physical={c['plug']:c for c in cal['physical_controls']};base_index={p:i for i,p in enumerate(base['plugs'])}
    if not values:raise ValueError('不能保存空表情样本')
    checked={}
    for p,v in values.items():
        if p not in base_index or p not in physical:raise ValueError('样本含不属于此角色的通道: '+p)
        v=float(v)
        if not math.isfinite(v) or not physical[p]['min']-1e-7<=v<=physical[p]['max']+1e-7:raise ValueError('控制器值超出限位: '+p)
        checked[p]=min(physical[p]['max'],max(physical[p]['min'],v))
    f=tracking['frames'][frame]
    sample=dict(id=sample_id or str(uuid.uuid4()),label=label or ('表情 %d'%frame),frame=frame,
        clip_id=s['clip_id'],time_seconds=float(f['time_seconds']),
        descriptor=descriptor(f,s['score_names'],tracking.get('width',1),tracking.get('height',1)),
        values=checked,baseline_values={p:base['values'][frame][base_index[p]] for p in checked},
        region=region,mode=mode,hard=bool(hard),enabled=True,radius=float(radius),time_radius_seconds=float(time_radius),
        mesh_snapshot=mesh_snapshot)
    existing=[i for i,a in enumerate(s['samples']) if a['id']==sample['id']]
    if sample_id and not existing:raise ValueError('要更新的样本不存在')
    if existing:s['samples'][existing[0]]=sample
    else:s['samples'].append(sample)
    s['revision']+=1;save(path,s);return sample


def delete_sample(path,sample_id):
    s=load(path);old=len(s['samples']);s['samples']=[a for a in s['samples'] if a['id']!=sample_id]
    if len(s['samples'])==old:raise ValueError('样本不存在')
    s['revision']+=1;save(path,s)


def set_enabled(path,sample_id,enabled):
    s=load(path);found=False
    for a in s['samples']:
        if a['id']==sample_id:a['enabled']=bool(enabled);found=True
    if not found:raise ValueError('样本不存在')
    s['revision']+=1;save(path,s)


def export_library(path,destination):
    s=load(path);save(destination,dict(schema=1,rig_signature=s['rig_signature'],score_names=s['score_names'],samples=s['samples']))


def import_library(path,source):
    s=load(path);library=load(source)
    if library.get('schema')!=1 or library.get('rig_signature')!=s['rig_signature'] or library.get('score_names')!=s['score_names']:
        raise ValueError('样本库的角色或描述特征不兼容')
    known={a['id'] for a in s['samples']}
    for sample in library['samples']:
        if sample['id'] not in known:s['samples'].append(sample);known.add(sample['id'])
    s['revision']+=1;save(path,s)


def suggestions(tracking):
    frames=[(i,f) for i,f in enumerate(tracking['frames']) if f.get('detected') and f.get('scores')]
    if not frames:return []
    criteria=[('中性参考',lambda f:-sum(f['scores'].get(k,0) for k in ('jawOpen','mouthSmileLeft','mouthSmileRight','eyeBlinkLeft','eyeBlinkRight'))),
        ('张嘴',lambda f:f['scores'].get('jawOpen',0)),('左闭眼',lambda f:f['scores'].get('eyeBlinkLeft',0)),
        ('右闭眼',lambda f:f['scores'].get('eyeBlinkRight',0)),('微笑',lambda f:f['scores'].get('mouthSmileLeft',0)+f['scores'].get('mouthSmileRight',0)),
        ('皱眉',lambda f:f['scores'].get('browDownLeft',0)+f['scores'].get('browDownRight',0)),
        ('抬眉',lambda f:f['scores'].get('browInnerUp',0)),('噘嘴',lambda f:f['scores'].get('mouthPucker',0))]
    return [dict(label=label,frame=max(frames,key=lambda pair:func(pair[1]))[0]) for label,func in criteria]
