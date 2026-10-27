"""Verify this computer's configured Maya and real rig in an isolated process."""
import datetime,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from faceinverse import config,session,project

def main():
    cfg=config.settings()
    if not Path(cfg['maya_python']).is_file():raise ValueError('Set the correct Maya mayapy path in project_paths.json.')
    if not cfg.get('scene') or not Path(cfg['scene']).is_file():raise ValueError('Select a neutral rig scene in the UI and Save Settings before VERIFY_MAYA.')
    output=ROOT/'work'/'maya_validation'/datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    output.mkdir(parents=True)
    session.save(output/'job.json',dict(mode='calibrate',config=cfg,output=str(output/'calibration.json')),False)
    project.invoke(cfg['maya_python'],['-m','faceinverse.maya_worker',output/'job.json'],output,'maya')
    cal=session.load(output/'calibration.json')
    report=dict(passed=True,maya=cal.get('host_maya'),python=cal.get('host_python'),branches=len(cal['variables']),
        controls=len({v['physical_index'] for v in cal['variables']}),max_sampled_mesh_response_cm=max(abs(v) for row in cal['mesh_matrix'] for v in row),
        note='Rig responsiveness only; does not certify video expression accuracy.',folder=str(output))
    session.save(ROOT/'work'/'verify_maya.json',report,False)
    print(json.dumps(report,indent=2));return 0

if __name__=='__main__':
    try:sys.exit(main())
    except Exception as exc:print('Maya validation failed: '+str(exc));sys.exit(1)
