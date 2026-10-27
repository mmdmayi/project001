param([switch]$Unattended)
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
Set-Location $root
$manifest=Get-Content (Join-Path $PSScriptRoot 'payload_manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$archive=Join-Path $root 'payload/python-3.12.10-embed-amd64.zip'
New-Item -ItemType Directory -Force (Join-Path $root 'payload'),(Join-Path $root 'work') | Out-Null
if (-not (Test-Path $archive)) {
    & curl.exe -L --fail --retry 2 --max-time 600 $manifest.python.url -o $archive
    if ($LASTEXITCODE -ne 0) { throw 'Cannot download Python runtime' }
}
$sha=[Security.Cryptography.SHA256]::Create()
$stream=[IO.File]::OpenRead($archive)
try { $hash=([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-','').ToLowerInvariant() } finally { $stream.Dispose();$sha.Dispose() }
if ($hash -ne $manifest.python.sha256) { throw 'Python runtime integrity check failed' }
$runtime=Join-Path $root '.runtime/python'
New-Item -ItemType Directory -Force $runtime | Out-Null
if (-not (Test-Path (Join-Path $runtime 'python.exe'))) { [Reflection.Assembly]::LoadWithPartialName('System.IO.Compression.FileSystem') | Out-Null; [IO.Compression.ZipFile]::ExtractToDirectory($archive,$runtime) }
[IO.File]::WriteAllText((Join-Path $runtime 'python312._pth'),"python312.zip`n.`nLib/site-packages`n$root`nimport site`n",(New-Object Text.UTF8Encoding($false)))
$env:PYTHONUTF8='1';$env:MPLCONFIGDIR=Join-Path $root 'work/mpl';$env:OPENBLAS_NUM_THREADS='1'
& (Join-Path $runtime 'python.exe') (Join-Path $PSScriptRoot 'bootstrap.py')
if ($LASTEXITCODE -ne 0) { throw 'Private runtime setup failed. See console details.' }
& (Join-Path $runtime 'python.exe') (Join-Path $PSScriptRoot 'verify_install.py')
if ($LASTEXITCODE -ne 0) { throw 'Installed runtime verification failed' }
