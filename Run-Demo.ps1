$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$taskPython = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) {
    & python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python environment creation failed.' }
}
& $taskPython -m pip install -e .
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
& $taskPython -m portfolio_engine demo --fast --out reports/demo
if ($LASTEXITCODE -ne 0) { throw 'Demo failed. Please read the error above.' }
Invoke-Item -LiteralPath (Join-Path $PSScriptRoot 'reports/demo/report.html')
