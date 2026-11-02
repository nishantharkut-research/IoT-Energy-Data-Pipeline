param(
    [Parameter(Mandatory = $true)]
    [string]$MachineMetadata,
    [string]$RuntimeRoot = $env:PIPELINE_RUNTIME_DIR,
    [Parameter(Mandatory = $true)]
    [ValidateSet('RUN-DESIGNATED-MACHINE-EXPERIMENTS')]
    [string]$Confirm,
    [string]$Python = $env:PIPELINE_PYTHON
)

$ErrorActionPreference = 'Stop'
if (-not $RuntimeRoot) { throw 'Provide -RuntimeRoot or PIPELINE_RUNTIME_DIR.' }
$repository = Split-Path -Parent $PSScriptRoot
$machinePath = (Resolve-Path -LiteralPath $MachineMetadata).Path
if (-not $Python) { $Python = Join-Path $repository '.venv/Scripts/python.exe' }
$pythonPath = (Get-Command $Python -ErrorAction Stop).Source
Push-Location -LiteralPath $repository
try {
    & $pythonPath -m iot_energy_pipeline.fixture_acceptance `
        --machine-metadata $machinePath `
        --runtime-root $RuntimeRoot `
        --repository $repository `
        --python $pythonPath `
        --confirm $Confirm
    $executionExitCode = $LASTEXITCODE
} finally {
    Pop-Location
}
exit $executionExitCode
