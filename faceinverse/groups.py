"""Authorable channel masks. Group changes do not rewrite recorded sample values."""
import copy
from . import session

def defaults(plugs):
    return {key:dict(name=name,plugs=[p for p in plugs if session.channel_region(p)==key])
        for key,name in (('brows','眉毛'),('eyes','眼睛'),('mouth','嘴和鼻'),('jaw','下颌'),('other','其他'))}

def available(info,plugs):
    return copy.deepcopy(info['groups'] if 'groups' in info else defaults(plugs))

def validate(groups,cal):
    allowed={c['plug'] for c in cal['physical_controls']}
    for key,group in groups.items():
        if not key or not group.get('name') or not isinstance(group.get('plugs'),list):raise ValueError('分组格式无效')
        if len(set(group['plugs']))!=len(group['plugs']):raise ValueError('分组控制器重复')
        if any(p not in allowed for p in group['plugs']):raise ValueError('只能添加该项目已标定的 Faceboard 通道；其他通道需重新标定')

def channels(info,plugs,region,selected=None):
    if not region.startswith('group:'):return session.choose_channels(plugs,region,selected)
    group=available(info,plugs).get(region[6:])
    if not group:raise ValueError('分组不存在')
    if any(p not in plugs for p in group['plugs']):raise ValueError('分组含尚未扩展到项目的通道')
    result=[p for p in plugs if p in group['plugs']]
    if not result:raise ValueError('该分组没有控制器，请先添加')
    return result
