param([string]$Python = 'python')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $projectRoot
try {
    & $Python -c "import sys; assert sys.version_info >= (3, 11), 'Python 3.11 minimum requis'"
    if ($LASTEXITCODE -ne 0) { throw 'Interpréteur Python incompatible.' }
    if (-not (Test-Path -LiteralPath '.venv-local/Scripts/python.exe')) {
        & $Python -m venv .venv-local
        if ($LASTEXITCODE -ne 0) { throw 'Création de l’environnement Python impossible.' }
    }
    & '.\.venv-local\Scripts\python.exe' -m pip install -r requirements-lock.txt
    if ($LASTEXITCODE -ne 0) { throw 'Installation Python échouée.' }
    Push-Location -LiteralPath 'frontend'
    try {
        & npm.cmd ci --cache .npm-cache
        if ($LASTEXITCODE -ne 0) { throw 'Installation frontend échouée.' }
        & npm.cmd run build
        if ($LASTEXITCODE -ne 0) { throw 'Compilation frontend échouée.' }
    } finally { Pop-Location }
    Write-Host 'Installation terminée. Lancer scripts/run.ps1.'
} finally { Pop-Location }
