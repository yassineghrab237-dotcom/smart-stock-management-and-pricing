param([int]$Port = 8000, [switch]$Dev, [string]$Database = 'runtime/stock.sqlite3')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$previousDatabase = [Environment]::GetEnvironmentVariable('SMART_STOCK_DB', 'Process')
$previousDev = [Environment]::GetEnvironmentVariable('SMART_STOCK_DEV', 'Process')
Push-Location -LiteralPath $projectRoot
try {
    if (-not (Test-Path -LiteralPath '.venv-local/Scripts/python.exe')) { throw 'Exécuter scripts/setup.ps1 avant le lancement.' }
    if (-not (Test-Path -LiteralPath 'frontend/dist/index.html')) { throw 'Compiler le frontend avec npm.cmd run build dans frontend.' }
    $databasePath = if ([IO.Path]::IsPathRooted($Database)) { $Database } else { Join-Path $projectRoot $Database }
    $env:SMART_STOCK_DB = [IO.Path]::GetFullPath($databasePath)
    $env:SMART_STOCK_DEV = if ($Dev) { '1' } else { '0' }
    Write-Host "Application locale : http://127.0.0.1:$Port ; arrêt avec Ctrl+C."
    & '.\.venv-local\Scripts\python.exe' -m uvicorn services.api_gateway.app.main:app --host 127.0.0.1 --port $Port
    if ($LASTEXITCODE -ne 0) { throw 'Le serveur s’est arrêté avec une erreur.' }
} finally {
    [Environment]::SetEnvironmentVariable('SMART_STOCK_DB', $previousDatabase, 'Process')
    [Environment]::SetEnvironmentVariable('SMART_STOCK_DEV', $previousDev, 'Process')
    Pop-Location
}
