"""Main-thread pose capture and sample application; no scientific imports."""
from maya import cmds
from . import session
from . import maya_bridge as m


def capture_current(path,index,label,region='all',selected=None,mode='pose',hard=True,radius=2.,time_radius=.5,sample_id=None):
    s,cal,tracking,base=session.inputs(path)
    if not 0<=index<len(base['frames']):raise ValueError('视频帧越界')
    frame=base['frames'][index]
    if abs(cmds.currentTime(query=True)-frame)>1e-4:raise ValueError('请先将 Maya 时间对齐到当前视频帧，再调整并记录表情')
    chosen=session.choose_channels(base['plugs'],region,selected)
    values={p:cmds.getAttr(p) for p in chosen if cmds.objExists(p)}
    if len(values)!=len(chosen):raise ValueError('当前 Maya 场景缺少项目控制器，请打开本项目动画场景')
    snapshot=None
    if cal.get('mesh') and cmds.objExists(cal['mesh']):
        snapshot=dict(mesh=cal['mesh'],vertices=cal['mesh_vertices'],reference=cal.get('reference'),
                      values=m.features(cal['mesh'],cal['mesh_vertices'],cal.get('reference')))
    return session.capture(path,index,values,label,region,mode,hard,radius,time_radius,sample_id,snapshot)


def apply_sample(path,sample_id):
    s,cal,tracking,base=session.inputs(path);sample=next(a for a in s['samples'] if a['id']==sample_id)
    if sample['clip_id']!=s['clip_id']:raise ValueError('跨片段样本没有当前时间定位，请在本片段重新记录，或仅用于表情计算')
    frame=base['frames'][sample['frame']];cmds.currentTime(frame)
    m.bake(dict(plugs=list(sample['values']),frames=[frame],values=[list(sample['values'].values())]))
