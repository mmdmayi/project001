"""Conservative action CANDIDATES; blendshape proxies are not validated FACS AU labels."""
import math,statistics

def _geometry(row,width,height):
    p=row.get('landmarks')
    if not p or len(p)<387:return None
    def xy(i):return p[i][0]*width,p[i][1]*height
    left,right=xy(33),xy(263);dx,dy=right[0]-left[0],right[1]-left[1];span=math.hypot(dx,dy)
    if span<1e-8:return None
    down=(-dy/span,dx/span)
    if down[1]<0:down=(-down[0],-down[1])
    mid=tuple((a+b)/2 for a,b in zip(xy(13),xy(14)))
    lift=sum(sum((mid[k]-xy(i)[k])*down[k] for k in (0,1)) for i in (61,291))/(2*span)
    gap=abs(sum((xy(14)[k]-xy(13)[k])*down[k] for k in (0,1)))/span
    return lift,gap

def candidates(tracking,threshold=.35):
    frames=tracking['frames'];fps=tracking['fps'];valid=[i for i,f in enumerate(frames) if f.get('detected') and f.get('scores')]
    if not valid:return []
    valid_set=set(valid)
    score=lambda i,k:float(frames[i]['scores'].get(k,0))
    criteria=[('jawOpen','张嘴 / AU26线索',lambda i:score(i,'jawOpen')),
        ('eyeBlinkLeft','左闭眼 / AU45线索',lambda i:score(i,'eyeBlinkLeft')),
        ('eyeBlinkRight','右闭眼 / AU45线索',lambda i:score(i,'eyeBlinkRight')),
        ('mouthSmile','嘴角拉起 / AU12线索',lambda i:max(score(i,'mouthSmileLeft'),score(i,'mouthSmileRight'))),
        ('browDown','眉压低 / AU4线索',lambda i:max(score(i,'browDownLeft'),score(i,'browDownRight'))),
        ('browInnerUp','内眉抬起 / AU1线索',lambda i:score(i,'browInnerUp')),
        ('mouthPucker','噘嘴 / AU18线索',lambda i:score(i,'mouthPucker'))]
    geometry={i:_geometry(frames[i],tracking.get('width',1),tracking.get('height',1)) for i in valid}
    neutral=[i for i in valid if max(score(i,k) for k in ('jawOpen','mouthSmileLeft','mouthSmileRight','eyeBlinkLeft','eyeBlinkRight'))<.18]
    anchor=statistics.median([geometry[i][0] for i in neutral if geometry[i] is not None]) if any(geometry[i] is not None for i in neutral) else None
    out=[]
    if neutral:
        i=min(neutral,key=lambda n:sum(score(n,k) for k in ('jawOpen','mouthSmileLeft','mouthSmileRight','eyeBlinkLeft','eyeBlinkRight')))
        out.append(dict(label='低活动候选（需确认中性）',frame=i,score=0.,action='low_activity',evidence='仅在已观察通道低活动；不是完整 FACS 中性判定'))
    for action,label,value in criteria:
        acceptable=[]
        for i in valid:
            v=value(i)
            if not math.isfinite(v) or v<threshold:continue
            # Reject isolated detections/spikes; blinks can be only 2 frames at low FPS.
            neighbors=[j for j in (i-1,i+1) if j in valid_set and abs(frames[j]['time_seconds']-frames[i]['time_seconds'])<=max(.12,2/fps)]
            if not any(value(j)>=threshold*.65 for j in neighbors):continue
            if action=='mouthSmile':
                g=geometry[i]
                # A low or static score maximum is not sufficient to name a smile.
                if anchor is None or g is None or g[0]-anchor<.01 or g[1]>.20:continue
            acceptable.append(i)
        if acceptable:
            i=max(acceptable,key=value)
            out.append(dict(label=label+'（待确认）',frame=i,score=value(i),action=action,
                evidence='模型系数阈值+邻帧支持'+(' + 相对低活动参考嘴角上升' if action=='mouthSmile' else ''),
                facs_status='AU-related model proxy; no certified FACS intensity or emotion inference'))
    return out
