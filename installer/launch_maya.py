import json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
from faceinverse import config
cfg=config.settings();mayapy=Path(cfg.get('maya_python',''))
exe=mayapy.with_name('maya.exe')
if not exe.is_file():raise SystemExit('Maya 2024 was not found. Set maya_python in project_paths.json or start scripts/launch_ui.py from Maya.')
script=ROOT/'scripts'/'launch_ui.py'
python='import runpy;runpy.run_path('+ascii(str(script).replace('\\','/'))+')'
mel='python('+json.dumps(python)+');'
subprocess.Popen([str(exe),'-command',mel])
print('Started Maya with FaceInverse. A Maya license and the character rig plugins are required.')
