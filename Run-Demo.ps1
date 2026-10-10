$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
& python (Join-Path $PSScriptRoot 'try_demo.py')
if ($LASTEXITCODE -ne 0) { throw '教学未完成，请查看上方原因和 README。' }
