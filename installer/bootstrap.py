"""Install fixed dependencies into the private embedded runtime, offline when available."""
import hashlib,json,os,subprocess,sys,urllib.request,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SITE=ROOT/'.runtime'/'python'/'Lib'/'site-packages'


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def download(asset,destination):
    destination=Path(destination);destination.parent.mkdir(parents=True,exist_ok=True)
    if destination.is_file() and digest(destination)==asset['sha256']:return
    url=asset.get('url')
    if not url:
        with urllib.request.urlopen(asset['metadata_url'],timeout=60) as response:metadata=json.load(response)
        url=next(a['url'] for a in metadata['urls'] if a['filename']==asset['filename'])
    urls=[url]
    if 'files.pythonhosted.org' in url:urls.append(url.replace('files.pythonhosted.org','pypi.tuna.tsinghua.edu.cn'))
    last=None
    for url in urls:
        try:
            with urllib.request.urlopen(url,timeout=90) as response,open(destination.with_suffix('.download'),'wb') as out:
                while True:
                    block=response.read(1024*1024)
                    if not block:break
                    out.write(block)
            temporary=destination.with_suffix('.download')
            if digest(temporary)!=asset['sha256']:raise ValueError('Integrity verification failed: '+asset['filename'])
            os.replace(temporary,destination);return
        except Exception as exc:last=exc
    raise RuntimeError('Download failed: '+asset['filename']+' '+str(last))


def main():
    manifest=json.loads((ROOT/'installer'/'payload_manifest.json').read_text(encoding='utf8'))
    house=ROOT/'payload'/'wheelhouse';house.mkdir(parents=True,exist_ok=True);SITE.mkdir(parents=True,exist_ok=True)
    for asset in manifest['bootstrap']:
        wheel=house/asset['filename'];download(asset,wheel)
        with zipfile.ZipFile(wheel) as archive:
            for member in archive.namelist():
                target=(SITE/member).resolve()
                if not target.is_relative_to(SITE.resolve()):raise ValueError('Unsafe wheel member')
            archive.extractall(SITE)
    offline=all((house/a['filename']).is_file() for a in manifest['wheels'])
    if offline:
        for asset in manifest['wheels']:
            if digest(house/asset['filename'])!=asset['sha256']:raise ValueError('Wheel hash mismatch: '+asset['filename'])
    args=[sys.executable,'-m','pip','install','--disable-pip-version-check','--upgrade','--no-build-isolation','--target',str(SITE),'-r',str(ROOT/'requirements-runtime.lock.txt')]
    if offline:args+=['--no-index','--find-links',str(house),'--only-binary=:all:']
    else:args+=['--index-url','https://pypi.tuna.tsinghua.edu.cn/simple','--find-links',str(house),'--timeout','30','--retries','1','--progress-bar','off']
    env=dict(os.environ);env['PIP_CACHE_DIR']=str(ROOT/'work'/'pip_cache');env['PYTHONUTF8']='1'
    import importlib.metadata
    expected=[line.strip().split('==') for line in (ROOT/'requirements-runtime.lock.txt').read_text(encoding='utf8').splitlines() if '==' in line]
    try:already=all(importlib.metadata.version(name)==version for name,version in expected)
    except importlib.metadata.PackageNotFoundError:already=False
    result=subprocess.CompletedProcess(args,0) if already else subprocess.run(args,env=env)
    if result.returncode and not offline:
        args[args.index('https://pypi.tuna.tsinghua.edu.cn/simple')]='https://pypi.org/simple';result=subprocess.run(args,env=env)
    if result.returncode:raise RuntimeError('Dependency installation failed')
    model=manifest['model'];download(model,ROOT/'models'/'face_landmarker.task')
    from faceinverse import config,session
    settings_file=ROOT/'project_paths.json'
    if not settings_file.exists():
        settings=config.defaults();settings['ffmpeg']=config.ffmpeg_path();session.save(settings_file,settings,False)
    report=dict(installed=True,offline_dependencies=offline,python=sys.version,root=str(ROOT))
    session.save(ROOT/'work'/'installation_report.json',report,False)
    print('Installation complete. Run VERIFY.bat, then OPEN_MAYA_TOOL.bat.')


if __name__=='__main__':main()
