"""Runtime discovery; Maya uses its own Python, computation uses private Python 3.12."""
import json,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SUPPORTED_MAYA=('2022','2024')

def target_maya():
    path=ROOT/'release.json'
    year=str(json.loads(path.read_text(encoding='utf-8-sig')).get('target_maya','2024')) if path.is_file() else '2024'
    if year not in SUPPORTED_MAYA:raise ValueError('Unsupported Maya release target: '+year)
    return year

def python_executable(video=False):
    portable=ROOT/'.runtime'/'python'/'python.exe'
    if portable.is_file():return str(portable)
    candidate=ROOT/('.venv-video' if video else '.venv-solver')/'Scripts'/'python.exe'
    if candidate.is_file():return str(candidate)
    if sys.version_info[:2]==(3,12):return sys.executable
    raise RuntimeError('外部运行环境未安装，请先运行 INSTALL.bat')

def defaults():
    year=target_maya()
    program=Path(os.environ.get('ProgramFiles',r'C:\Program Files'))
    maya=program/'Autodesk'/('Maya'+year)/'bin'/'mayapy.exe'
    epic=program/'Epic Games'/'MetaHumanForMaya'/'lib'/'riglogic4_maya'
    matches=sorted(epic.glob('*/maya-'+year+'/plugin/embeddedRL4.mll')) if epic.exists() else []
    return dict(maya_python=str(maya),maya_version=year,plugin=str(matches[-1]) if matches else '',scene='',gui_root='gui',
                mesh='head_lod0_mesh',reference='head_grp',raw_node='CTRL_expressions',ffmpeg='',allow_newer_scene=False)

def settings():
    out=defaults();path=ROOT/'project_paths.json'
    if path.is_file():out.update(json.loads(path.read_text(encoding='utf-8-sig')))
    return out

def ffmpeg_path(config=None):
    path=(config or {}).get('ffmpeg','')
    if path and Path(path).is_file():return path
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:return ''
