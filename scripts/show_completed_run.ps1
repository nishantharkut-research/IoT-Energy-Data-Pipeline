param(
    [string]$RunId = 'correctness-combined-r01',
    [string]$Python = 'python',
    [int]$Port = 8501
)
$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot -Parent
$runtime = Join-Path $repo 'reports/runtime/full-assumed-hkt-20261028-003'
$allowed = Get-ChildItem $runtime -Directory | Where-Object {
    Test-Path (Join-Path $_.FullName 'run-manifest.sha256')
}
$selected = $allowed | Where-Object Name -EQ $RunId
if (-not $selected) { throw 'Choose an existing sealed run directory name.' }
$env:IOT_ENERGY_RUN_DIR = $selected.FullName
$env:PYTHONPATH = (Join-Path $repo 'src') + ';' + $repo
Push-Location $repo
try {
    & $Python -m streamlit run dashboard/app.py --server.port $Port --theme.base light
    if ($LASTEXITCODE -ne 0) { throw 'Dashboard exited with an error.' }
} finally { Pop-Location }
