"""Maya 2022 / 2024 main-thread adapter; standard library + Maya API only."""
import contextlib
import hashlib
import json
import math
from maya import cmds
from maya.api import OpenMaya as om


def write(path, value):
    with open(path, 'w', encoding='utf8') as f:
        json.dump(value, f, indent=2, allow_nan=False)


def read(path):
    with open(path, encoding='utf8') as f:
        return json.load(f)


def scan(root):
    """Candidates only. Review limits / neutral before calibration."""
    nodes = [root] + (cmds.listRelatives(root, allDescendents=True, fullPath=True, type='transform') or [])
    found = []
    for node in nodes:
        # MetaHuman Faceboard handles may use polygon shapes, not NURBS curves.
        shapes = cmds.listRelatives(node, shapes=True) or []
        if not shapes or not (cmds.listRelatives(node,shapes=True,type='nurbsCurve') or
                              node.split('|')[-1].split(':')[-1].startswith('CTRL_')):
            continue
        for attr in cmds.listAttr(node, keyable=True, scalar=True) or []:
            plug = node+'.'+attr
            if cmds.getAttr(plug, type=True) not in ('double','float','doubleLinear','doubleAngle'):
                continue
            if not cmds.getAttr(plug, settable=True) or cmds.listConnections(plug, source=True, destination=False):
                continue
            value = cmds.getAttr(plug)
            lower = cmds.attributeQuery(attr, node=node, minimum=True) if cmds.attributeQuery(attr,node=node,minExists=True) else None
            upper = cmds.attributeQuery(attr, node=node, maximum=True) if cmds.attributeQuery(attr,node=node,maxExists=True) else None
            axis_flags = {'translateX':'tx','translateY':'ty','translateZ':'tz',
                          'rotateX':'rx','rotateY':'ry','rotateZ':'rz',
                          'scaleX':'sx','scaleY':'sy','scaleZ':'sz'}
            if attr in axis_flags:
                flag = axis_flags[attr]
                limits = cmds.transformLimits(node,query=True,**{flag:True})
                enabled = cmds.transformLimits(node,query=True,**{'e'+flag:True})
                if enabled[0]: lower=[limits[0]]
                if enabled[1]: upper=[limits[1]]
            found.append(dict(plug=plug, neutral=value, min=lower[0] if lower else None,
                              max=upper[0] if upper else None))
    return found


def validate_controls(controls):
    if not controls or len({c['plug'] for c in controls}) != len(controls):
        raise ValueError('Controls must be nonempty and unique')
    for c in controls:
        if not all(isinstance(c[k], (int,float)) and math.isfinite(c[k]) for k in ('min','max','neutral')):
            raise ValueError('Review missing limits: '+c['plug'])
        if not c['min'] <= c['neutral'] <= c['max'] or c['min'] == c['max']:
            raise ValueError('Invalid control range')
        if not cmds.objExists(c['plug']) or not cmds.getAttr(c['plug'],settable=True):
            raise ValueError('Unavailable control: '+c['plug'])
        if cmds.listConnections(c['plug'],source=True,destination=False):
            raise ValueError('Calibration requires unconnected controls: '+c['plug'])


@contextlib.contextmanager
def preserved(controls):
    values = [cmds.getAttr(c['plug']) for c in controls]
    frame = cmds.currentTime(query=True)
    auto = cmds.autoKeyframe(query=True,state=True)
    try:
        cmds.autoKeyframe(state=False)
        yield
    finally:
        for c,v in zip(controls,values): cmds.setAttr(c['plug'],v)
        cmds.currentTime(frame)
        cmds.autoKeyframe(state=auto)


def apply(controls, values):
    for c,v in zip(controls,values): cmds.setAttr(c['plug'],v)


def features(mesh, vertices, reference=None):
    selection = om.MSelectionList(); selection.add(mesh)
    path = selection.getDagPath(0)
    if path.apiType() == om.MFn.kTransform: path.extendToShape()
    points = om.MFnMesh(path).getPoints(om.MSpace.kWorld)
    if not vertices or len(set(vertices)) != len(vertices): raise ValueError('Unique vertex IDs required')
    inverse = None
    if reference:
        sel = om.MSelectionList(); sel.add(reference)
        inverse = sel.getDagPath(0).inclusiveMatrixInverse()
    out = []
    for index in vertices:
        if index < 0 or index >= len(points): raise ValueError('Vertex out of range')
        p = points[index] * inverse if inverse is not None else points[index]
        out.extend((p.x,p.y,p.z))
    return out


def calibrate(profile, fraction=0.25):
    controls = profile['controls']; validate_controls(controls)
    if not 0 < fraction <= 1: raise ValueError('Invalid sampling fraction')
    sample = lambda: features(profile['mesh'],profile['vertices'],profile.get('reference'))
    c0 = [c['neutral'] for c in controls]
    columns, diagnostics = [], []
    with preserved(controls):
        apply(controls,c0); neutral = sample()
        for i,c in enumerate(controls):
            low = max(c['min'], c0[i] - fraction*(c['max']-c['min']))
            high = min(c['max'], c0[i] + fraction*(c['max']-c['min']))
            v = list(c0); v[i] = low; apply(controls,v); a = sample()
            v[i] = high; apply(controls,v); b = sample()
            columns.append([(y-x)/(high-low) for x,y in zip(a,b)])
            diagnostics.append(dict(plug=c['plug'],low=low,high=high,
                                    response_norm=math.sqrt(sum((y-x)**2 for x,y in zip(a,b))),
                                    neutral_chord_error=math.sqrt(sum(
                                        (n-(x+(y-x)*(c0[i]-low)/(high-low)))**2
                                        for n,x,y in zip(neutral,a,b)))))
            apply(controls,c0)
    if not any(d['response_norm'] > 1e-10 for d in diagnostics):
        raise ValueError('All mesh responses are zero; verify evaluated rig and feature IDs')
    return dict(schema=1, controls=controls, neutral=neutral,
                matrix=[list(row) for row in zip(*columns)], profile=profile,
                profile_hash=hashlib.sha256(json.dumps(profile,sort_keys=True).encode()).hexdigest(),
                diagnostics=diagnostics, units=cmds.currentUnit(query=True,linear=True))


def sample_poses(profile, poses, frames):
    validate_controls(profile['controls'])
    if len(poses) != len(frames): raise ValueError('Pose/frame count mismatch')
    rows = []
    with preserved(profile['controls']):
        for pose in poses:
            if len(pose) != len(profile['controls']): raise ValueError('Pose width mismatch')
            apply(profile['controls'],pose)
            rows.append(features(profile['mesh'],profile['vertices'],profile.get('reference')))
    return dict(schema=1,frames=frames,features=rows)


def bake(result):
    plugs, frames, rows = result['plugs'], result['frames'], result['values']
    if len(rows) != len(frames) or not frames or len(set(plugs)) != len(plugs):
        raise ValueError('Invalid animation dimensions')
    if any(b <= a for a,b in zip(frames,frames[1:])): raise ValueError('Invalid frame order')
    for row in rows:
        if len(row) != len(plugs) or not all(math.isfinite(v) for v in row): raise ValueError('Invalid animation values')
    for plug in plugs:
        if not cmds.objExists(plug) or cmds.getAttr(plug,lock=True): raise ValueError('Missing/locked plug '+plug)
        incoming = cmds.listConnections(plug,source=True,destination=False) or []
        if any(not cmds.nodeType(n).startswith('animCurve') for n in incoming):
            raise ValueError('Driven channel cannot be baked: '+plug)
    cmds.undoInfo(openChunk=True,chunkName='FaceInverse bake')
    try:
        for frame,row in zip(frames,rows):
            for plug,value in zip(plugs,row):
                cmds.setKeyframe(plug,time=frame,value=value,inTangentType='linear',outTangentType='linear')
    finally:
        cmds.undoInfo(closeChunk=True)
