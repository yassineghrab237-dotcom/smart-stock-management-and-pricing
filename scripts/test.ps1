$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $projectRoot
try {
    & '.\.venv-local\Scripts\python.exe' -m pytest tests -q
    if ($LASTEXITCODE -ne 0) { throw 'Tests serveur échoués.' }
    & '.\.venv-local\Scripts\python.exe' -m pip check
    if ($LASTEXITCODE -ne 0) { throw 'Dépendances Python incompatibles.' }
    Push-Location -LiteralPath 'frontend'
    try {
        & npm.cmd run build
        if ($LASTEXITCODE -ne 0) { throw 'Compilation frontend échouée.' }
    } finally { Pop-Location }
    & git diff --check
    if ($LASTEXITCODE -ne 0) { throw 'Diff invalide.' }
} finally { Pop-Location }
