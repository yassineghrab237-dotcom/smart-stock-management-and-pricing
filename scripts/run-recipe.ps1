param([int]$Port = 8000, [switch]$New)
$ErrorActionPreference='Stop'
$projectRoot=Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $projectRoot
$previousDemo=[Environment]::GetEnvironmentVariable('SMART_STOCK_DEMO','Process')
try {
    if ($New -or -not (Test-Path -LiteralPath 'runtime/latest-recipe.json')) {
        & '.\.venv-local\Scripts\python.exe' scripts/create_recipe.py
        if ($LASTEXITCODE -ne 0) {throw 'Préparation de recette échouée.'}
    }
    $recipe=Get-Content -LiteralPath 'runtime/latest-recipe.json' -Raw | ConvertFrom-Json
    Write-Host "Accès de démonstration : $($recipe.access_file)"
    $env:SMART_STOCK_DEMO='1'
    & '.\scripts\run.ps1' -Port $Port -Database $recipe.database
} finally {
    [Environment]::SetEnvironmentVariable('SMART_STOCK_DEMO',$previousDemo,'Process')
    Pop-Location
}
