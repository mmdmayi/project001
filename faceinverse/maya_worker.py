"""Isolated Maya worker: sample a rig, or bake an already computed animation."""
import base64,os,sys,json,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))

def run(job_path):
    from .session import load,save
    job=load(job_path);output=Path(job['output']);output.parent.mkdir(parents=True,exist_ok=True)
    os.environ['MAYA_APP_DIR']=str(output.parent/'maya_profile');os.environ['MAYA_DISABLE_CIP']='1';os.environ['MAYA_DISABLE_CER']='1';os.environ['QT_QPA_PLATFORM']='offscreen'
    import maya.standalone
    maya.standalone.initialize(name='python')
    from maya import cmds
    from maya.api import OpenMaya as om
    from . import maya_bridge as m
    config=job['config'];started=time.perf_counter()
    try:
        actual_maya=str(cmds.about(version=True))
        if actual_maya not in ('2022','2024'):raise ValueError('Unsupported Maya host: '+actual_maya)
        expected=str(config.get('maya_version',actual_maya))
        if expected!=actual_maya:raise ValueError('Maya version mismatch: expected '+expected+', running '+actual_maya)
        plugin=config.get('plugin')
        if plugin:cmds.loadPlugin(plugin,quiet=True)
        cmds.file(config['scene'],open=True,force=True,prompt=False,executeScriptNodes=False,ignoreVersion=bool(config.get('allow_newer_scene',False)))
        if job['mode']=='calibrate':
            from .semantic_map import observations
            raw=config.get('raw_node','CTRL_expressions');mesh=config.get('mesh','head_lod0_mesh');ref=config.get('reference') or None
            root=config.get('gui_root','gui')
            if not cmds.objExists(raw) or not cmds.objExists(mesh) or not cmds.objExists(root):raise ValueError('角色缺少已配置的 Faceboard、Mesh 或表情诊断节点')
            names=[n for n in observations() if cmds.objExists(raw+'.'+n)]
            if not names:raise ValueError('角色没有可采样的表情诊断属性')
            controls=[c for c in m.scan(root) if c['min'] is not None and c['max'] is not None and c['min']<c['max']
                and c['plug'].endswith(('.translateX','.translateY')) and ('Tweakers' not in c['plug'] or '_mouth_lipsRoll' in c['plug'].split('|')[-1])
                and all(x not in c['plug'] for x in ('tongue','teeth','neck','CTRL_C_eye.','followHead','FollowHead'))]
            m.validate_controls(controls);rows=lambda:[cmds.getAttr(raw+'.'+n) for n in names]
            sel=om.MSelectionList();sel.add(mesh);dag=sel.getDagPath(0)
            if dag.apiType()==om.MFn.kTransform:dag.extendToShape()
            count=om.MFnMesh(dag).numVertices;vertices=list(range(0,count,max(1,count//200)))
            c0=[c['neutral'] for c in controls];variables=[];columns=[];mesh_columns=[]
            with m.preserved(controls):
                m.apply(controls,c0);neutral=rows();mesh0=m.features(mesh,vertices,ref)
                for i,c in enumerate(controls):
                    for sign in (1,-1):
                        bound=c['max']-c['neutral'] if sign>0 else c['neutral']-c['min']
                        if bound<=1e-8:continue
                        pose=list(c0);pose[i]+=sign*bound;m.apply(controls,pose)
                        delta=[a-b for a,b in zip(rows(),neutral)]
                        if max(map(abs,delta),default=0)<1e-8:continue
                        variables.append(dict(plug=c['plug'],sign=sign,amplitude=bound,physical_index=i));columns.append(delta)
                        mesh_columns.append([a-b for a,b in zip(m.features(mesh,vertices,ref),mesh0)])
                    m.apply(controls,c0)
            if not variables:raise ValueError('Faceboard 没有有效响应')
            if not any(abs(value)>1e-7 for column in mesh_columns for value in column):
                raise ValueError('RIG_NO_MESH_RESPONSE: 面部没有实际变形，请检查角色执行插件、Mesh 和绑定评价')
            save(output,dict(schema=1,physical_controls=controls,variables=variables,observation_names=names,neutral=neutral,
                matrix=[list(r) for r in zip(*columns)],mesh=mesh,reference=ref,mesh_vertices=vertices,mesh_neutral=mesh0,
                mesh_matrix=[list(r) for r in zip(*mesh_columns)],host_maya=actual_maya,host_python=sys.version,raw_node=raw,mapping=observations(),config=config,seconds=time.perf_counter()-started),False)
        elif job['mode']=='bake':
            result=load(job['animation']);cmds.currentUnit(time='film');m.bake(result)
            if job.get('audio') and Path(job['audio']).is_file():cmds.sound(file=job['audio'],offset=result['frames'][0],name='FaceInverse_reference_audio')
            error=0.
            for i in sorted({0,len(result['frames'])//4,len(result['frames'])//2,len(result['frames'])-1}):
                cmds.currentTime(result['frames'][i])
                error=max(error,max(abs(cmds.getAttr(p)-v) for p,v in zip(result['plugs'],result['values'][i])))
            if error>1e-5:raise RuntimeError('关键帧回放校验失败')
            cmds.playbackOptions(minTime=result['frames'][0],maxTime=result['frames'][-1])
            cmds.currentTime(result['frames'][0]);cmds.file(rename=str(output));cmds.file(save=True,type='mayaBinary',force=True)
            save(output.with_suffix('.verification.json'),dict(host_maya=actual_maya,host_python=sys.version,key_error=error,keys=cmds.keyframe(result['plugs'],query=True,keyframeCount=True),seconds=time.perf_counter()-started),False)
        else:raise ValueError('Unknown Maya worker mode')
    finally:maya.standalone.uninitialize()

if __name__=='__main__':
    encoded=os.environ.get('FACEINVERSE_JOB_B64')
    run(base64.b64decode(encoded).decode('utf8') if encoded else sys.argv[1])
