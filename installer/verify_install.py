"""Check the installed private runtime; never imports Maya's Python into it."""
import importlib,json,os,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['MPLCONFIGDIR']=str(ROOT/'work'/'mpl');os.environ['OPENBLAS_NUM_THREADS']='1'
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))

def main():
    versions={}
    for name in ('numpy','scipy','cv2','mediapipe','pyrender','imageio_ffmpeg'):
        module=importlib.import_module(name);versions[name]=getattr(module,'__version__','imported')
    import mediapipe as mp
    options=mp.tasks.vision.FaceLandmarkerOptions(base_options=mp.tasks.BaseOptions(model_asset_buffer=(ROOT/'models'/'face_landmarker.task').read_bytes()))
    with mp.tasks.vision.FaceLandmarker.create_from_options(options):pass
    (ROOT/'work').mkdir(exist_ok=True)
    tests=unittest.defaultTestLoader.discover(str(ROOT/'tests'),pattern='test_*.py',top_level_dir=str(ROOT))
    result=unittest.TextTestRunner(verbosity=1).run(tests)
    from faceinverse import config,session
    session.save(ROOT/'work'/'verify_install.json',dict(passed=result.wasSuccessful(),tests=result.testsRun,versions=versions,
        executable=sys.executable,isolated=bool(sys.flags.isolated),sys_path=sys.path,root=str(ROOT),maya_detected=Path(config.settings().get('maya_python','')).is_file()),False)
    return 0 if result.wasSuccessful() else 1
if __name__=='__main__':sys.exit(main())
