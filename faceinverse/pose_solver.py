"""Expression-space sample learning plus exact temporal key constraints. External Python only."""
import argparse,copy,json
from pathlib import Path
import numpy as np
from scipy.linalg import solve_banded
from . import session


def kernel(distance):
    r=np.asarray(distance);return np.maximum(1.-r,0.)**4*(4.*r+1.)


def smooth_residual(values,anchors,amount):
    n=len(values)
    if amount<0 or not np.isfinite(amount):raise ValueError('Invalid smoothing')
    out=np.asarray(values,float).copy()
    if not n:return out
    if amount==0:
        for i,v in anchors.items():out[i]=v
        return out
    fixed=sorted(anchors);breaks=[-1]+fixed+[n]
    for i,v in anchors.items():out[i]=v
    for left,right in zip(breaks,breaks[1:]):
        start,end=left+1,right
        if end<=start:continue
        ids=np.arange(start,end);diagonal=1.+amount*(2.-(ids==0).astype(float)-(ids==n-1).astype(float))
        rhs=np.asarray(values[start:end],float).copy()
        if left>=0:rhs[0]+=amount*anchors[left]
        if right<n:rhs[-1]+=amount*anchors[right]
        ab=np.zeros((3,end-start));ab[1]=diagonal
        if end-start>1:ab[0,1:]=-amount;ab[2,:-1]=-amount
        out[start:end]=solve_banded((1,1),ab,rhs,check_finite=True)
    return out


def solve_samples(info,cal,tracking,base):
    out=copy.deepcopy(base);original=np.asarray(base['values'],float)
    if original.shape!=(len(tracking['frames']),len(base['plugs'])) or not np.isfinite(original).all():raise ValueError('Invalid baseline')
    valid=np.array([bool(f.get('detected')) for f in tracking['frames']]);n=len(valid)
    x=np.zeros((n,len(info['score_names'])+5))
    for i,f in enumerate(tracking['frames']):
        if valid[i]:x[i]=session.descriptor(f,info['score_names'],tracking.get('width',1),tracking.get('height',1))
    samples=[a for a in info['samples'] if a.get('enabled',True)]
    physical={c['plug']:c for c in cal['physical_controls']}
    index={p:i for i,p in enumerate(base['plugs'])}
    corrections=np.zeros_like(original);anchor_errors=[];changed=[];hard_by_channel={}
    times=np.asarray([f['time_seconds'] for f in tracking['frames']])
    for sample in samples:
        if len(sample['descriptor'])!=x.shape[1] or not np.isfinite(sample['descriptor']).all():raise ValueError('Invalid sample descriptor')
        for p,v in sample['values'].items():
            if p not in index or p not in physical or not np.isfinite(v) or not physical[p]['min']<=v<=physical[p]['max']:
                raise ValueError('Incompatible or out-of-range pose sample: '+p)
    for plug,j in index.items():
        chosen=[a for a in samples if plug in a['values'] and (a['mode']=='pose' or a['clip_id']==info['clip_id'])]
        if not chosen:continue
        changed.append(plug);anchors={};residual=np.zeros(n)
        for a in chosen:
            if a.get('hard',True) and a['clip_id']==info['clip_id']:
                i=int(a['frame'])
                if not 0<=i<n or not valid[i]:raise ValueError('Invalid key pose frame')
                value=a['values'][plug]-original[i,j]
                if i in anchors and abs(anchors[i]-value)>1e-7:raise ValueError('同一帧的硬约束冲突: '+plug)
                anchors[i]=value
        pose=[a for a in chosen if a['mode']=='pose']
        if pose:
            centers=np.asarray([a['descriptor'] for a in pose],float)
            scale=np.maximum(np.std(np.vstack((x[valid],centers)),axis=0),.05)
            active=np.ptp(np.vstack((x[valid],centers)),axis=0)>.005
            if not active.any():active[:]=True
            xx=x[:,active]/scale[active];cc=centers[:,active]/scale[active]
            distance=np.sqrt(np.mean((cc[:,None,:]-cc[None,:,:])**2,axis=2))
            radii=np.array([a['radius'] for a in pose]);radius=float(np.median(radii))
            if radius<=0 or not np.isfinite(radius):raise ValueError('Invalid sample radius')
            # Symmetric kernel uses the minimum per-pair support radius; per-sample radius remains meaningful.
            pair_radius=np.sqrt(radii[:,None]*radii[None,:])
            k=kernel(distance/pair_radius)
            targets=np.array([a['values'][plug]-a['baseline_values'][plug] for a in pose])
            for a in range(len(pose)):
                for b in range(a):
                    if distance[a,b]<1e-7 and abs(targets[a]-targets[b])>1e-4:
                        raise ValueError('相同表情存在互相矛盾的样本，请禁用冲突样本或改用局部模式: '+plug)
            coefficients=np.linalg.solve(k+np.eye(len(pose))*1e-6,targets)
            distances=np.sqrt(np.mean((xx[:,None,:]-cc[None,:,:])**2,axis=2))
            residual+=kernel(distances/radii[None,:])@coefficients
        local=[a for a in chosen if a['mode']=='local']
        if local:
            numerator=np.zeros(n);total=np.zeros(n)
            for a in local:
                radius=float(a['time_radius_seconds'])
                if radius<=0:raise ValueError('Invalid local support')
                weight=kernel(np.abs(times-a['time_seconds'])/radius)
                numerator+=weight*(a['values'][plug]-original[int(a['frame']),j]);total+=weight
            influence=np.minimum(total,1.)
            average=np.divide(numerator,total,out=np.zeros(n),where=total>1e-12)
            residual=residual*(1.-influence)+average*influence
        residual[~valid]=0.
        residual=smooth_residual(residual,anchors,float(info.get('settings',{}).get('smoothing',.12)))
        residual[~valid]=0.
        corrected=np.clip(original[:,j]+residual,physical[plug]['min'],physical[plug]['max'])
        for i,v in anchors.items():corrected[i]=original[i,j]+v
        corrections[:,j]=corrected-original[:,j];hard_by_channel[plug]=anchors
    values=original+corrections
    for plug,anchors in hard_by_channel.items():
        for i,residual in anchors.items():anchor_errors.append(abs(values[i,index[plug]]-(original[i,index[plug]]+residual)))
    out['values']=values.tolist();out['kind']='key-expression calibrated Faceboard animation'
    a=np.asarray(cal['matrix'],float);neutral=np.asarray(cal['neutral']);lookup={p:j for j,p in enumerate(base['plugs'])}
    effective=np.zeros((n,len(cal['variables'])))
    for k,v in enumerate(cal['variables']):
        c=cal['physical_controls'][v['physical_index']]
        delta=values[:,lookup[c['plug']]]-c['neutral'] if c['plug'] in lookup else np.zeros(n)
        effective[:,k]=np.clip(delta*v['sign']/v['amplitude'],0,1)
    predicted=effective@a.T+neutral
    out['predicted_observations']=predicted.tolist()
    if 'semantic_targets' in out:out['feature_rmse']=np.sqrt(np.mean((predicted-np.asarray(out['semantic_targets']))**2,axis=1)).tolist()
    out['key_expression_report']=dict(enabled_samples=len(samples),channels=changed,hard_constraints=len(anchor_errors),
        max_hard_error=max(anchor_errors,default=0.),max_control_change=float(np.max(np.abs(corrections))) if n else 0.,
        clip_id=info['clip_id'],revision=info['revision'],
        note='Expression-space residual fitting. Hard key agreement verifies authored constraints, not video ground-truth accuracy.')
    return out


def solve_file(path,output):
    info,cal,tracking,base=session.inputs(path);result=solve_samples(info,cal,tracking,base)
    session.save(output,result,backup=False);return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('session');p.add_argument('output');a=p.parse_args()
    result=solve_file(a.session,a.output);print(json.dumps(result['key_expression_report']),flush=True)
