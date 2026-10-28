"""Start the separate tracker using the selected Maya's bundled PySide2 only."""
import base64,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from faceinverse import config

def main():
    cfg=config.settings();mayapy=Path(cfg['maya_python'])
    if not mayapy.is_file():raise ValueError('Maya mayapy not found; configure project_paths.json first.')
    env=dict(os.environ);env.pop('PYTHONHOME',None);env['MAYA_PYTHON_VERSION']='3';env['PYTHONPATH']=str(ROOT)
    env['FACEINVERSE_ROOT_B64']=base64.b64encode(str(ROOT).encode('utf8')).decode('ascii')
    env['QT_PLUGIN_PATH']=str(mayapy.parent.parent/'plugins')
    if '--smoke' in sys.argv:env['FACEINVERSE_TRACKER_SMOKE']='1'
    bootstrap="import os,sys,base64,runpy;sys.path.insert(0,base64.b64decode(os.environ['FACEINVERSE_ROOT_B64']).decode('utf8'));runpy.run_module('faceinverse.tracker_ui',run_name='__main__')"
    (ROOT/'work').mkdir(exist_ok=True)
    with open(ROOT/'work/tracker_ui.log','a',encoding='utf8') as log:
        subprocess.Popen([str(mayapy),'-c',bootstrap],env=env,stdout=log,stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    print('Tracker started. Computation uses the private external runtime.')

if __name__=='__main__':main()
