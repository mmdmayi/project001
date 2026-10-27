"""Bounded semantic video retarget baseline using sampled existing Faceboard responses.
This is NOT pixel/3D geometric reconstruction. Identity gains remain an editable approximation.
"""
import argparse,json,time
from pathlib import Path
import numpy as np
from scipy.optimize import lsq_linear


def fill_missing(rows,names,fps):
    valid=np.array([bool(r.get('detected')) and bool(r.get('scores')) for r in rows])
    if not valid.any():raise ValueError('No detected faces in clip')
    out=np.zeros((len(rows),len(names)));quality=['detected' if v else 'missing' for v in valid]
    for i,row in enumerate(rows):
        if valid[i]:out[i]=[row['scores'].get(n,0.) for n in names]
    index=0
    while index<len(rows):
        if valid[index]:index+=1;continue
        end=index
        while end<len(rows) and not valid[end]:end+=1
        left=index-1;gap=end-index
        if left>=0 and end<len(rows) and gap<=3:
            for k in range(index,end):
                a=(k-left)/(end-left);out[k]=(1-a)*out[left]+a*out[end];quality[k]='interpolated_short_gap'
        else:
            for k in range(index,end):
                if left<0:out[k]=0.;quality[k]='neutral_before_detection'
                else:
                    elapsed=(k-left)/fps;factor=max(0.,1.-max(0.,elapsed-.25)/.25)
                    out[k]=out[left]*factor;quality[k]='held_then_faded'
        index=end
    return out,valid,quality



def landmark_assist(normalized,score_names,rows,tracking,neutral_frame=None):
    """Editable geometric heuristics for large mouth opening / closure / closed-mouth corners.
    Ratios remove image scale and in-plane roll; they are not actor/rig 3D registration.
    """
    w,h=tracking.get('width',1),tracking.get('height',1)
    measured=[];indices=[]
    for i,row in enumerate(rows):
        points=row.get('landmarks')
        if not row.get('detected') or points is None or len(points)<387:continue
        p=np.asarray(points,float)*[w,h,w]
        horizontal=p[263,:2]-p[33,:2];span=np.linalg.norm(horizontal)
        if span<1e-8:continue
        down=np.array([-horizontal[1],horizontal[0]])/span
        if down[1]<0:down=-down
        gap=abs(np.dot(p[14,:2]-p[13,:2],down))/span
        eye_r=abs(np.dot(p[145,:2]-p[159,:2],down))/max(np.linalg.norm(p[133,:2]-p[33,:2]),1e-8)
        eye_l=abs(np.dot(p[374,:2]-p[386,:2],down))/max(np.linalg.norm(p[263,:2]-p[362,:2]),1e-8)
        mid=(p[13,:2]+p[14,:2])/2.
        lift_l=np.dot(mid-p[291,:2],down)/span
        lift_r=np.dot(mid-p[61,:2],down)/span
        measured.append([gap,eye_l,eye_r,lift_l,lift_r]);indices.append(i)
    if not measured:return normalized,{'applied':False}
    data=np.asarray(measured);open_ratios=np.clip(np.percentile(data[:,1:3],85,axis=0),.12,.6)
    if neutral_frame is not None and neutral_frame in indices:anchor=data[indices.index(neutral_frame)]
    else:anchor=np.median(data[:max(1,min(len(data),round(tracking['fps']*.5)))],axis=0)
    offsets=max(0.,float(np.percentile(data[:,0],5)))
    values=normalized.copy()
    def at(name):return score_names.index(name)
    for i,m in zip(indices,data):
        values[i,at('jawOpen')]=max(values[i,at('jawOpen')],np.clip((m[0]-offsets)/.35,0,1))
        for side,j in [('Left',0),('Right',1)]:
            blink=np.clip((1.-m[j+1]/open_ratios[j])/.85,0,1)
            values[i,at('eyeBlink'+side)]=max(values[i,at('eyeBlink'+side)],blink)
            if blink>.3:values[i,at('eyeWide'+side)]*=1.-blink
            if m[0]<.12:
                delta=m[j+3]-anchor[j+3]
                values[i,at('mouthSmile'+side)]=min(values[i,at('mouthSmile'+side)],np.clip((delta+.015)/.08,0,1))
                values[i,at('mouthFrown'+side)]=max(values[i,at('mouthFrown'+side)],np.clip((-delta-.01)/.10,0,1))
    # Reapply the same explicit gap policy after correcting detected frames.
    corrected=[dict(detected=r.get('detected',False),scores=dict(zip(score_names,values[i]))) for i,r in enumerate(rows)]
    values,_,_=fill_missing(corrected,score_names,float(tracking['fps']))
    return values,dict(applied=True,eye_open_ratios=open_ratios.tolist(),corner_reference=anchor[3:].tolist(),
        mouth_neutral_ratio=offsets,jaw_full_gap_ratio=.35,
        note='Heuristic ratio assistance; first 0.5s corner baseline unless explicit neutral frame. Not calibrated geometric reconstruction.')


def retarget(cal,tracking,neutral_frame=None,temporal=.02,assist=False):
    a=np.asarray(cal['matrix'],float);base=np.asarray(cal['neutral'],float)
    variables=cal['variables'];physical=cal['physical_controls'];obs=cal['observation_names']
    if a.shape!=(len(obs),len(variables)) or not np.isfinite(a).all():raise ValueError('Invalid response matrix')
    rows=tracking['frames'];fps=float(tracking['fps'])
    if not np.isfinite(fps) or fps<=0 or not rows:raise ValueError('Invalid tracking timebase')
    if not np.isfinite(temporal) or temporal<0:raise ValueError('Invalid temporal regularization')
    times=np.array([r['time_seconds'] for r in rows],float)
    if not np.isfinite(times).all() or np.any(np.diff(times)<=0):raise ValueError('Invalid timestamps')
    score_names=sorted({key for mapping in cal['mapping'].values() for key in mapping})
    scores,valid,quality=fill_missing(rows,score_names,fps)
    if not np.isfinite(scores).all():raise ValueError('Nonfinite video scores')
    if neutral_frame is None:
        offsets=np.minimum(np.percentile(scores[valid],5,axis=0),.15)
    else:
        if not 0<=neutral_frame<len(rows) or not valid[neutral_frame]:raise ValueError('Neutral frame must be detected')
        offsets=np.minimum(scores[neutral_frame],.5)
    normalized=np.clip((scores-offsets)/(1.-offsets),0.,1.)
    assist_report={'applied':False}
    if assist:normalized,assist_report=landmark_assist(normalized,score_names,rows,tracking,neutral_frame)
    # Preserve explicit gap behavior: do not normalize a faded missing row into invented detections.
    target=np.zeros((len(rows),len(obs)))
    for j,name in enumerate(obs):
        for score,gain in cal['mapping'].get(name,{}).items():target[:,j]+=normalized[:,score_names.index(score)]*gain
    target=np.clip(target,0.,1.)
    weights=np.array([2. if n.startswith(('eyeBlink','jawOpen')) else 1. for n in obs])
    used=sorted({v['physical_index'] for v in variables});plugs=[physical[i]['plug'] for i in used]
    reg=1e-4;time_weight=temporal*(fps/24.)**2
    identity=np.eye(len(variables));matrix=np.vstack((a*weights[:,None],np.sqrt(reg)*identity,np.sqrt(time_weight)*identity))
    previous=np.zeros(len(variables));values=[];errors=[];statuses=[];predictions=[]
    started=time.perf_counter()
    for row in target:
        rhs=np.concatenate(((row-base)*weights,np.zeros(len(variables)),np.sqrt(time_weight)*previous))
        result=lsq_linear(matrix,rhs,bounds=(0.,1.),method='bvls',tol=1e-8,max_iter=200)
        if not result.success:raise RuntimeError(result.message)
        delta=np.zeros(len(physical))
        for z,v in zip(result.x,variables):delta[v['physical_index']]+=z*v['sign']*v['amplitude']
        control=[float(np.clip(physical[i]['neutral']+delta[i],physical[i]['min'],physical[i]['max'])) for i in used]
        # Enforce the physical signed channel: opposite virtual branches cannot coexist.
        effective=np.array([max(0.,delta[v['physical_index']]*v['sign'])/v['amplitude'] for v in variables])
        effective=np.clip(effective,0.,1.);previous=effective
        predicted=a@effective+base
        values.append(control);predictions.append(predicted.tolist());errors.append(float(np.sqrt(np.mean((predicted-row)**2))))
        statuses.append(int(result.status))
    return dict(schema=2,kind='video-driven Faceboard semantic baseline',plugs=plugs,frames=(1.+24.*times).tolist(),
        values=values,source_fps=fps,scene_fps=24.,source=tracking.get('source'),source_start_seconds=tracking.get('source_start_seconds',0.),
        detection_flags=valid.tolist(),quality=quality,observation_names=obs,semantic_targets=target.tolist(),
        predicted_observations=predictions,feature_rmse=errors,statuses=statuses,seconds=time.perf_counter()-started,
        neutral_policy='explicit_frame' if neutral_frame is not None else '5th percentile lower envelope capped at 0.15',
        neutral_offsets=dict(zip(score_names,offsets.tolist())),semantic_mapping=cal['mapping'],landmark_assistance=assist_report,
        unobservable_rows=[name for name,column in zip(obs,a) if np.linalg.norm(column)<1e-8],
        note='Approximate expression-space retarget; not actor-specific geometric reconstruction. No ground-truth performance accuracy implied.')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('calibration');p.add_argument('tracking');p.add_argument('output')
    group=p.add_mutually_exclusive_group();group.add_argument('--landmark-assist',action='store_true',help='Explicitly enable legacy uncalibrated amplitude heuristics');group.add_argument('--no-landmark-assist',action='store_true');p.add_argument('--neutral-frame',type=int);p.add_argument('--temporal',type=float,default=.02);args=p.parse_args()
    cal=json.loads(Path(args.calibration).read_text(encoding='utf-8-sig'));tracking=json.loads(Path(args.tracking).read_text(encoding='utf-8-sig'))
    result=retarget(cal,tracking,args.neutral_frame,args.temporal,args.landmark_assist and not args.no_landmark_assist)
    Path(args.output).parent.mkdir(parents=True,exist_ok=True);Path(args.output).write_text(json.dumps(result,allow_nan=False),encoding='utf8')
    print(json.dumps(dict(output=args.output,frames=len(result['frames']),controls=len(result['plugs']),seconds=result['seconds'],
                         mean_semantic_rmse=float(np.mean(result['feature_rmse'])),unobservable=result['unobservable_rows'])),flush=True)
